"""
Задачи Celery для управления статусами сотрудников
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from organization_management.apps.statuses.application.services import StatusApplicationService
from organization_management.apps.statuses.models import EmployeeStatus

logger = logging.getLogger(__name__)


@shared_task(name='statuses.apply_planned_statuses')
def apply_planned_statuses_task():
    """
    Автоматическое применение запланированных статусов

    Задача выполняется ежедневно и активирует все статусы,
    дата начала которых наступила
    """
    service = StatusApplicationService()

    try:
        applied_statuses = service.apply_planned_statuses()

        logger.info(
            f"Применено запланированных статусов: {len(applied_statuses)}"
        )

        # Отправляем уведомления о примененных статусах
        for status in applied_statuses:
            send_status_applied_notification.delay(status.id)

        return {
            'success': True,
            'applied_count': len(applied_statuses),
            'statuses': [status.id for status in applied_statuses]
        }

    except Exception as e:
        logger.error(f"Ошибка при применении запланированных статусов: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='statuses.complete_expired_statuses')
def complete_expired_statuses_task():
    """
    Автоматическое завершение истекших статусов

    Задача выполняется ежедневно и завершает все статусы,
    дата окончания которых истекла
    """
    service = StatusApplicationService()

    try:
        completed_statuses = service.complete_expired_statuses()

        logger.info(
            f"Завершено истекших статусов: {len(completed_statuses)}"
        )

        # Отправляем уведомления о завершенных статусах
        for status in completed_statuses:
            send_status_completed_notification.delay(status.id)

        return {
            'success': True,
            'completed_count': len(completed_statuses),
            'statuses': [status.id for status in completed_statuses]
        }

    except Exception as e:
        logger.error(f"Ошибка при завершении истекших статусов: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='statuses.send_upcoming_status_notifications')
def send_upcoming_status_notifications_task(days_before: int = 7):
    """
    Отправка уведомлений о предстоящих статусах

    Args:
        days_before: За сколько дней до начала статуса отправлять уведомление

    Задача выполняется ежедневно и отправляет уведомления
    о статусах, которые начнутся через N дней
    """
    today = timezone.now().date()
    notification_date = today + timedelta(days=days_before)

    try:
        # Находим запланированные статусы, которые начнутся через N дней
        upcoming_statuses = EmployeeStatus.objects.filter(
            state=EmployeeStatus.StatusState.PLANNED,
            start_date=notification_date,
            is_notified=False
        ).select_related('employee', 'created_by')

        notifications_sent = 0

        for status in upcoming_statuses:
            try:
                send_upcoming_status_notification.delay(status.id, days_before)

                # Отмечаем, что уведомление отправлено
                status.is_notified = True
                status.save(update_fields=['is_notified'])

                notifications_sent += 1
            except Exception as e:
                logger.error(
                    f"Ошибка при отправке уведомления для статуса {status.id}: {str(e)}"
                )

        logger.info(
            f"Отправлено уведомлений о предстоящих статусах: {notifications_sent}"
        )

        return {
            'success': True,
            'notifications_sent': notifications_sent,
            'days_before': days_before
        }

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о предстоящих статусах: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='statuses.send_upcoming_status_notification')
def send_upcoming_status_notification(status_id: int, days_before: int):
    """
    Отправка уведомления о предстоящем статусе конкретному сотруднику

    Args:
        status_id: ID статуса
        days_before: За сколько дней до начала
    """
    try:
        status = EmployeeStatus.objects.select_related(
            'employee',
            'created_by',
            'related_division'
        ).get(pk=status_id)

        # Импортируем сервис уведомлений
        from organization_management.apps.notifications.models import Notification

        # Создаем уведомление для сотрудника
        if status.employee.user:
            notification = Notification.objects.create(
                user=status.employee.user,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title=f"Предстоящее изменение статуса",
                message=(
                    f"Через {days_before} дней ({status.start_date}) у вас будет установлен статус "
                    f"'{status.get_status_type_display()}'"
                    f"{f' до {status.end_date}' if status.end_date else ''}."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )
            logger.info(f"Уведомление о предстоящем статусе отправлено: {notification.id}")

        # Уведомляем руководителя (если есть)
        if status.created_by and status.created_by != status.employee.user:
            Notification.objects.create(
                user=status.created_by,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title=f"Напоминание о статусе сотрудника",
                message=(
                    f"Через {days_before} дней ({status.start_date}) у сотрудника "
                    f"{status.employee} будет установлен статус "
                    f"'{status.get_status_type_display()}'"
                    f"{f' до {status.end_date}' if status.end_date else ''}."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )

        return {'success': True, 'status_id': status_id}

    except EmployeeStatus.DoesNotExist:
        logger.error(f"Статус {status_id} не найден")
        return {'success': False, 'error': 'Status not found'}
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о предстоящем статусе {status_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='statuses.send_status_applied_notification')
def send_status_applied_notification(status_id: int):
    """
    Отправка уведомления о применении статуса

    Args:
        status_id: ID статуса
    """
    try:
        status = EmployeeStatus.objects.select_related('employee').get(pk=status_id)

        from organization_management.apps.notifications.models import Notification

        # Уведомляем сотрудника
        if status.employee.user:
            Notification.objects.create(
                user=status.employee.user,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title="Изменение статуса",
                message=(
                    f"Ваш статус изменен на '{status.get_status_type_display()}' "
                    f"с {status.start_date}"
                    f"{f' по {status.end_date}' if status.end_date else ''}."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )

        logger.info(f"Уведомление о применении статуса {status_id} отправлено")
        return {'success': True, 'status_id': status_id}

    except EmployeeStatus.DoesNotExist:
        logger.error(f"Статус {status_id} не найден")
        return {'success': False, 'error': 'Status not found'}
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о применении статуса {status_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='statuses.send_status_completed_notification')
def send_status_completed_notification(status_id: int):
    """
    Отправка уведомления о завершении статуса

    Args:
        status_id: ID статуса
    """
    try:
        status = EmployeeStatus.objects.select_related('employee').get(pk=status_id)

        from organization_management.apps.notifications.models import Notification

        # Уведомляем сотрудника
        if status.employee.user:
            Notification.objects.create(
                user=status.employee.user,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title="Завершение статуса",
                message=(
                    f"Ваш статус '{status.get_status_type_display()}' завершен. "
                    f"Текущий статус: 'В строю'."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )

        logger.info(f"Уведомление о завершении статуса {status_id} отправлено")
        return {'success': True, 'status_id': status_id}

    except EmployeeStatus.DoesNotExist:
        logger.error(f"Статус {status_id} не найден")
        return {'success': False, 'error': 'Status not found'}
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о завершении статуса {status_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='statuses.send_status_extended_notification')
def send_status_extended_notification(status_id: int):
    """
    Отправка уведомления о продлении статуса

    Args:
        status_id: ID статуса
    """
    try:
        status = EmployeeStatus.objects.select_related('employee', 'created_by').get(pk=status_id)

        from organization_management.apps.notifications.models import Notification

        # Уведомляем сотрудника
        if status.employee.user:
            Notification.objects.create(
                user=status.employee.user,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title="Продление статуса",
                message=(
                    f"Ваш статус '{status.get_status_type_display()}' продлен до {status.end_date}."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )

        # Уведомляем руководителя
        if status.created_by and status.created_by != status.employee.user:
            Notification.objects.create(
                user=status.created_by,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title="Продление статуса сотрудника",
                message=(
                    f"Статус '{status.get_status_type_display()}' сотрудника "
                    f"{status.employee} продлен до {status.end_date}."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )

        logger.info(f"Уведомление о продлении статуса {status_id} отправлено")
        return {'success': True, 'status_id': status_id}

    except EmployeeStatus.DoesNotExist:
        logger.error(f"Статус {status_id} не найден")
        return {'success': False, 'error': 'Status not found'}
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о продлении статуса {status_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='statuses.send_ending_status_notifications')
def send_ending_status_notifications_task(days_before: int = 3):
    """
    Отправка уведомлений о скором окончании длительных статусов

    Args:
        days_before: За сколько дней до окончания отправлять уведомление

    Задача выполняется ежедневно и отправляет уведомления
    о статусах, которые завершатся через N дней
    """
    today = timezone.now().date()
    notification_date = today + timedelta(days=days_before)

    # Типы статусов, для которых отправляем уведомления
    long_term_status_types = [
        EmployeeStatus.StatusType.VACATION,
        EmployeeStatus.StatusType.BUSINESS_TRIP,
        EmployeeStatus.StatusType.TRAINING,
        EmployeeStatus.StatusType.SECONDED_FROM,
        EmployeeStatus.StatusType.SECONDED_TO,
    ]

    try:
        # Находим активные статусы, которые завершатся через N дней
        ending_statuses = EmployeeStatus.objects.filter(
            state=EmployeeStatus.StatusState.ACTIVE,
            status_type__in=long_term_status_types,
            end_date=notification_date
        ).select_related('employee', 'created_by')

        notifications_sent = 0

        for status in ending_statuses:
            try:
                send_ending_status_notification.delay(status.id, days_before)
                notifications_sent += 1
            except Exception as e:
                logger.error(
                    f"Ошибка при отправке уведомления о завершении статуса {status.id}: {str(e)}"
                )

        logger.info(
            f"Отправлено уведомлений о завершающихся статусах: {notifications_sent}"
        )

        return {
            'success': True,
            'notifications_sent': notifications_sent,
            'days_before': days_before
        }

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о завершающихся статусах: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='statuses.send_ending_status_notification')
def send_ending_status_notification(status_id: int, days_before: int):
    """
    Отправка уведомления о скором окончании статуса

    Args:
        status_id: ID статуса
        days_before: За сколько дней до окончания
    """
    try:
        status = EmployeeStatus.objects.select_related(
            'employee',
            'created_by',
            'related_division'
        ).get(pk=status_id)

        from organization_management.apps.notifications.models import Notification

        # Создаем уведомление для сотрудника
        if status.employee.user:
            notification = Notification.objects.create(
                user=status.employee.user,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title=f"Скоро завершится статус",
                message=(
                    f"Через {days_before} дней ({status.end_date}) завершится ваш статус "
                    f"'{status.get_status_type_display()}'. "
                    f"Начало: {status.start_date}."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )
            logger.info(f"Уведомление о завершении статуса отправлено: {notification.id}")

        # Уведомляем руководителя
        if status.created_by and status.created_by != status.employee.user:
            Notification.objects.create(
                user=status.created_by,
                notification_type=Notification.NotificationType.STATUS_CHANGE,
                title="Скоро завершится статус сотрудника",
                message=(
                    f"Через {days_before} дней ({status.end_date}) завершится статус "
                    f"'{status.get_status_type_display()}' сотрудника {status.employee}. "
                    f"Начало: {status.start_date}."
                ),
                related_object_id=status.id,
                related_object_type='employee_status'
            )

        return {'success': True, 'status_id': status_id}

    except EmployeeStatus.DoesNotExist:
        logger.error(f"Статус {status_id} не найден")
        return {'success': False, 'error': 'Status not found'}
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о завершении статуса {status_id}: {str(e)}")
        return {'success': False, 'error': str(e)}
