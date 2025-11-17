"""
Сигналы для автоматической обработки статусов
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from organization_management.apps.employees.models import Employee
from organization_management.apps.statuses.models import EmployeeStatus, StatusChangeHistory


@receiver(pre_save, sender=Employee)
def close_statuses_on_dismissal(sender, instance, **kwargs):
    """
    Автоматическое закрытие всех активных статусов при увольнении сотрудника

    Срабатывает при изменении статуса занятости на 'Уволен' или
    при установке даты увольнения
    """
    # Проверяем, существует ли объект в БД (не новый объект)
    if not instance.pk:
        return

    try:
        # Получаем старое состояние объекта из БД
        old_employee = Employee.objects.get(pk=instance.pk)
    except Employee.DoesNotExist:
        return

    # Проверяем, изменился ли статус на "Уволен" или установлена дата увольнения
    is_being_dismissed = (
        (instance.employment_status == Employee.EmploymentStatus.FIRED and
         old_employee.employment_status != Employee.EmploymentStatus.FIRED) or
        (instance.dismissal_date and not old_employee.dismissal_date)
    )

    if not is_being_dismissed:
        return

    # Получаем дату увольнения
    dismissal_date = instance.dismissal_date or timezone.now().date()

    # Находим активные статусы (завершаем)
    active_statuses = EmployeeStatus.objects.filter(
        employee=instance,
        state=EmployeeStatus.StatusState.ACTIVE
    )

    # Завершаем активные статусы
    for status in active_statuses:
        status.actual_end_date = dismissal_date
        status.state = EmployeeStatus.StatusState.COMPLETED
        status.early_termination_reason = f"Автоматически завершен в связи с увольнением сотрудника ({dismissal_date})"
        status._skip_history_log = True  # Пропускаем автоматическое логирование
        status.save()

        # Создаем запись в истории вручную с более подробной информацией
        StatusChangeHistory.objects.create(
            status=status,
            change_type=StatusChangeHistory.ChangeType.TERMINATED,
            comment=f"Автоматически завершен при увольнении сотрудника"
        )

    # Находим будущие (запланированные) статусы (отменяем)
    planned_statuses = EmployeeStatus.objects.filter(
        employee=instance,
        state=EmployeeStatus.StatusState.PLANNED
    )

    # Отменяем запланированные статусы
    for status in planned_statuses:
        # Используем метод cancel модели
        status.cancel(
            reason=f"Автоматически отменен в связи с увольнением сотрудника ({dismissal_date})",
            user=None
        )


@receiver(post_save, sender=EmployeeStatus)
def log_status_change(sender, instance, created, **kwargs):
    """
    Автоматическое создание записи в истории изменений при создании или изменении статуса

    Это гарантирует, что все изменения статусов логируются в StatusChangeHistory,
    даже если они создаются через API без явного вызова методов модели
    """
    # Пропускаем, если запись истории уже создается внутри методов модели
    # (чтобы избежать дублирования)
    if getattr(instance, '_skip_history_log', False):
        return

    # Определяем пользователя из контекста (если доступен)
    changed_by = instance.created_by if created else getattr(instance, '_changed_by', None)

    if created:
        # Создание нового статуса
        StatusChangeHistory.objects.create(
            status=instance,
            change_type=StatusChangeHistory.ChangeType.CREATED,
            changed_by=changed_by,
            comment=f"Создан статус '{instance.get_status_type_display()}' ({instance.start_date} - {instance.end_date or 'н/д'})"
        )
    else:
        # Изменение существующего статуса
        StatusChangeHistory.objects.create(
            status=instance,
            change_type=StatusChangeHistory.ChangeType.MODIFIED,
            changed_by=changed_by,
            comment=f"Статус '{instance.get_status_type_display()}' изменен"
        )
