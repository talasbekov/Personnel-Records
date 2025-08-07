"""
Celery задачи для приложения управления персоналом.

Реализация автоматизированных процессов согласно ТЗ:
- Эскалация при несвоевременном обновлении статусов
- Автоматическое копирование статусов
- Возврат к статусу "В строю" по истечении периода
- Уведомления и проверки
"""

import datetime
from typing import List, Dict, Optional

from celery import shared_task
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    Division, Employee, EmployeeStatusLog, DivisionStatusUpdate,
    UserProfile, UserRole, EmployeeStatusType, DivisionType,
    EscalationRule
)
from notifications.models import Notification, NotificationType
from audit.models import AuditLog


@shared_task
def check_status_updates_task():
    """
    Проверка обновления статусов и эскалация.

    Запускается в 14:00, 16:00 и 18:00 согласно ТЗ.
    """
    current_time = timezone.now()
    today = current_time.date()
    hour = current_time.hour

    # Определяем уровень эскалации
    if hour >= 18:
        escalation_level = 3
        auto_copy = True
    elif hour >= 16:
        escalation_level = 2
        auto_copy = False
    else:  # hour >= 14
        escalation_level = 1
        auto_copy = False

    # Получаем подразделения, которые не обновили статусы
    all_divisions = Division.objects.filter(
        division_type__in=[DivisionType.MANAGEMENT, DivisionType.OFFICE]
    )

    not_updated_divisions = []
    for division in all_divisions:
        status_update = DivisionStatusUpdate.objects.filter(
            division=division,
            update_date=today
        ).first()

        if not status_update or not status_update.is_updated:
            not_updated_divisions.append(division)

    if not not_updated_divisions:
        return "Все подразделения обновили статусы"

    # Создаем уведомления в зависимости от уровня эскалации
    if escalation_level == 1:
        # Уведомляем начальников департаментов (Роль-2)
        _notify_department_heads(not_updated_divisions, today)
    elif escalation_level == 2:
        # Уведомляем администраторов системы (Роль-4)
        _notify_system_admins(not_updated_divisions, today)
    else:  # escalation_level == 3
        # Автоматическое копирование статусов
        if auto_copy:
            _auto_copy_statuses_for_divisions(not_updated_divisions, today)
        # Блокировка генерации отчетов реализуется на уровне view

    # Логирование эскалации
    for division in not_updated_divisions:
        AuditLog.objects.create(
            action_type='ESCALATION',
            payload={
                'division_id': division.id,
                'division_name': division.name,
                'date': str(today),
                'escalation_level': escalation_level,
                'auto_copied': auto_copy
            }
        )

    return f"Обработано {len(not_updated_divisions)} подразделений с уровнем эскалации {escalation_level}"


@shared_task
def copy_statuses_task(target_date: Optional[str] = None):
    """
    Копирование статусов сотрудников на следующий день.

    Запускается ежедневно в 00:05 и 18:10.
    """
    if target_date:
        try:
            today = datetime.date.fromisoformat(target_date)
        except ValueError:
            return "Неверный формат даты"
    else:
        today = timezone.now().date()

    yesterday = today - datetime.timedelta(days=1)

    # Получаем всех активных сотрудников
    active_employees = Employee.objects.filter(is_active=True)
    copied_count = 0
    skipped_count = 0

    with transaction.atomic():
        for employee in active_employees:
            # Проверяем, есть ли уже статус на сегодня
            has_status_today = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=today,
                is_auto_copied=False  # Только ручные статусы
            ).exists()

            if has_status_today:
                skipped_count += 1
                continue

            # Получаем статус на вчера
            yesterday_status = employee.status_logs.filter(
                date_from__lte=yesterday
            ).filter(
                Q(date_to__gte=yesterday) | Q(date_to__isnull=True)
            ).order_by('-date_from', '-id').first()

            if not yesterday_status:
                skipped_count += 1
                continue

            # Не копируем статус "В строю" - это статус по умолчанию
            if yesterday_status.status == EmployeeStatusType.ON_DUTY_SCHEDULED:
                skipped_count += 1
                continue

            # Проверяем, не истек ли срок статуса
            if yesterday_status.date_to and yesterday_status.date_to < today:
                skipped_count += 1
                continue

            # Проверяем идемпотентность
            already_copied = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=today,
                status=yesterday_status.status,
                is_auto_copied=True
            ).exists()

            if already_copied:
                skipped_count += 1
                continue

            # Копируем статус
            new_status = EmployeeStatusLog.objects.create(
                employee=employee,
                status=yesterday_status.status,
                date_from=today,
                date_to=today,  # Копируем на один день
                comment=f"Авто-копия с {yesterday}. {yesterday_status.comment or ''}",
                secondment_division=yesterday_status.secondment_division,
                is_auto_copied=True,
                created_by=None  # Системное действие
            )
            copied_count += 1

    return f"Скопировано статусов: {copied_count}, пропущено: {skipped_count}"


@shared_task
def reset_default_statuses_task():
    """
    Возврат сотрудников к статусу по умолчанию.

    Запускается ежедневно в 00:10.
    """
    today = timezone.now().date()
    yesterday = today - datetime.timedelta(days=1)

    # Находим статусы, которые закончились вчера
    expired_logs = EmployeeStatusLog.objects.filter(
        date_to=yesterday,
        status__in=[
            EmployeeStatusType.ON_LEAVE,
            EmployeeStatusType.SICK_LEAVE,
            EmployeeStatusType.BUSINESS_TRIP,
            EmployeeStatusType.TRAINING_ETC,
            EmployeeStatusType.AFTER_DUTY
        ]
    ).select_related('employee')

    reset_count = 0

    with transaction.atomic():
        for log in expired_logs:
            employee = log.employee

            # Проверяем, нет ли уже нового статуса
            has_new_status = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=today
            ).exists()

            if has_new_status:
                continue

            # Создаем статус "В строю"
            EmployeeStatusLog.objects.create(
                employee=employee,
                status=EmployeeStatusType.ON_DUTY_SCHEDULED,
                date_from=today,
                comment="Автоматический возврат в строй",
                is_auto_copied=False,
                created_by=None
            )
            reset_count += 1

    return f"Возвращено в строй: {reset_count} сотрудников"


@shared_task
def send_weekend_planning_reminder():
    """
    Напоминание о планировании на выходные.

    Запускается по пятницам в 15:00.
    """
    today = timezone.now().date()

    # Проверяем, что сегодня пятница
    if today.weekday() != 4:  # 4 = пятница
        return "Не пятница, напоминание не отправлено"

    # Получаем всех пользователей с ролями 3 и 6
    profiles = UserProfile.objects.filter(
        role__in=[UserRole.ROLE_3, UserRole.ROLE_6]
    ).select_related('user', 'division_assignment')

    notification_count = 0

    for profile in profiles:
        if not profile.division_assignment:
            continue

        Notification.objects.create(
            recipient=profile.user,
            notification_type=NotificationType.STATUS_UPDATE,
            title="Напоминание о планировании на выходные",
            message=(
                f"Не забудьте обновить статусы сотрудников {profile.division_assignment.name} "
                f"на субботу и воскресенье"
            ),
            payload={
                'division_id': profile.division_assignment.id,
                'dates': [
                    str(today + datetime.timedelta(days=1)),
                    str(today + datetime.timedelta(days=2))
                ]
            }
        )
        notification_count += 1

    return f"Отправлено {notification_count} напоминаний"


@shared_task
def check_secondment_expiry():
    """
    Проверка истечения срока прикомандирования.

    Запускается ежедневно.
    """
    today = timezone.now().date()
    tomorrow = today + datetime.timedelta(days=1)

    # Находим прикомандирования, которые истекают завтра
    expiring_logs = EmployeeStatusLog.objects.filter(
        status=EmployeeStatusType.SECONDED_OUT,
        date_to=tomorrow
    ).select_related('employee', 'secondment_division')

    notification_count = 0

    for log in expiring_logs:
        # Уведомляем начальника исходного подразделения
        managers = UserProfile.objects.filter(
            role=UserRole.ROLE_3,
            division_assignment=log.employee.division
        )

        for manager in managers:
            Notification.objects.create(
                recipient=manager.user,
                notification_type=NotificationType.SECONDMENT,
                title=f"Истекает срок прикомандирования {log.employee.full_name}",
                message=(
                    f"Завтра ({tomorrow}) истекает срок прикомандирования "
                    f"сотрудника {log.employee.full_name} в {log.secondment_division.name}"
                ),
                payload={
                    'employee_id': log.employee.id,
                    'division_id': log.secondment_division.id,
                    'expiry_date': str(tomorrow)
                }
            )
            notification_count += 1

    return f"Отправлено {notification_count} уведомлений об истечении прикомандирования"


@shared_task
def generate_daily_reports():
    """
    Автоматическая генерация ежедневных отчетов.

    Запускается в 19:00 для подразделений с включенной автогенерацией.
    """
    from .services import generate_personnel_report_docx
    from .models import PersonnelReport, ReportType

    today = timezone.now().date()
    tomorrow = today + datetime.timedelta(days=1)

    # Получаем департаменты для которых нужно генерировать отчеты
    departments = Division.objects.filter(
        division_type=DivisionType.DEPARTMENT
    )

    generated_count = 0

    for department in departments:
        # Проверяем, все ли управления обновили статусы
        managements = department.child_divisions.filter(
            division_type=DivisionType.MANAGEMENT
        )

        all_updated = True
        for management in managements:
            status = DivisionStatusUpdate.objects.filter(
                division=management,
                update_date=today
            ).first()

            if not status or not status.is_updated:
                all_updated = False
                break

        if not all_updated:
            continue

        # Генерируем отчет
        try:
            report_buffer = generate_personnel_report_docx(department, tomorrow)

            report = PersonnelReport.objects.create(
                division=department,
                report_date=tomorrow,
                report_type=ReportType.DAILY,
                date_from=tomorrow,
                date_to=tomorrow,
                file_format='docx',
                created_by=None  # Автоматическая генерация
            )

            filename = f'auto_report_{department.code}_{tomorrow}.docx'
            report.file.save(filename, report_buffer)

            generated_count += 1

        except Exception as e:
            # Логируем ошибку
            AuditLog.objects.create(
                action_type='REPORT_GENERATED',
                payload={
                    'error': str(e),
                    'division_id': department.id,
                    'date': str(tomorrow)
                }
            )

    return f"Сгенерировано {generated_count} отчетов"


# Вспомогательные функции

def _notify_department_heads(divisions: List[Division], date: datetime.date):
    """Уведомить начальников департаментов"""
    for division in divisions:
        # Находим родительский департамент
        parent = division.parent_division
        while parent and parent.division_type != DivisionType.DEPARTMENT:
            parent = parent.parent_division

        if not parent:
            continue

        # Находим начальников департамента
        heads = UserProfile.objects.filter(
            role=UserRole.ROLE_2,
            division_assignment=parent
        )

        for head in heads:
            Notification.objects.create(
                recipient=head.user,
                notification_type=NotificationType.ESCALATION,
                title=f"Статусы не обновлены: {division.name}",
                message=(
                    f"Подразделение {division.name} не обновило статусы "
                    f"сотрудников на {date}. Требуется ваше внимание."
                ),
                payload={
                    'division_id': division.id,
                    'date': str(date),
                    'escalation_level': 1
                }
            )


def _notify_system_admins(divisions: List[Division], date: datetime.date):
    """Уведомить администраторов системы"""
    admins = User.objects.filter(
        Q(is_superuser=True) | Q(profile__role=UserRole.ROLE_4)
    ).distinct()

    division_names = ', '.join([d.name for d in divisions[:5]])
    if len(divisions) > 5:
        division_names += f' и еще {len(divisions) - 5}'

    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            notification_type=NotificationType.ESCALATION,
            title="Критично: статусы не обновлены",
            message=(
                f"Следующие подразделения не обновили статусы на {date}: "
                f"{division_names}. Требуется срочное вмешательство."
            ),
            payload={
                'division_ids': [d.id for d in divisions],
                'date': str(date),
                'escalation_level': 2
            }
        )


def _auto_copy_statuses_for_divisions(divisions: List[Division], date: datetime.date):
    """Автоматическое копирование статусов для подразделений"""
    for division in divisions:
        # Получаем сотрудников подразделения
        employees = Employee.objects.filter(
            division=division,
            is_active=True
        )

        for employee in employees:
            # Используем логику из copy_statuses_task
            yesterday = date - datetime.timedelta(days=1)

            # Проверяем наличие статуса на сегодня
            has_status = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=date
            ).exists()

            if has_status:
                continue

            # Копируем вчерашний статус
            yesterday_status = employee.status_logs.filter(
                date_from__lte=yesterday
            ).filter(
                Q(date_to__gte=yesterday) | Q(date_to__isnull=True)
            ).order_by('-date_from', '-id').first()

            if yesterday_status and yesterday_status.status != EmployeeStatusType.ON_DUTY_SCHEDULED:
                EmployeeStatusLog.objects.create(
                    employee=employee,
                    status=yesterday_status.status,
                    date_from=date,
                    date_to=date,
                    comment=f"Авто-копия (эскалация). {yesterday_status.comment or ''}",
                    secondment_division=yesterday_status.secondment_division,
                    is_auto_copied=True,
                    created_by=None
                )

        # Отмечаем подразделение как обновленное
        DivisionStatusUpdate.objects.update_or_create(
            division=division,
            update_date=date,
            defaults={
                'is_updated': True,
                'updated_at': timezone.now(),
                'updated_by': None
            }
        )