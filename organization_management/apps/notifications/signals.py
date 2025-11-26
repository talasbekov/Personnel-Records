"""
Signal handlers for notifications.

These receivers listen to model events across the personnel
application and generate corresponding ``Notification`` records.  When
Channels is installed and properly configured, the receivers also
broadcast real-time messages over WebSocket so that clients can
immediately reflect state changes without polling.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from organization_management.apps.secondments.models import SecondmentRequest
# from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.employees.models import Employee
from .models import Notification

# Attempt Channels import
try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    _has_channels = True
except Exception:
    _has_channels = False


# ✅ Сигнал только на SecondmentRequest
@receiver(post_save, sender=SecondmentRequest, dispatch_uid="create_secondment_notification")
def create_secondment_notification(sender, instance, created, **kwargs):
    """
    Отправляет уведомление при создании новой заявки на прикомандирование.
    Уведомление отправляется пользователям, которые могут управлять принимающим подразделением (to_division).
    """
    if not created:
        return

    from organization_management.apps.notifications.services.websocket_service import send_notification
    from organization_management.apps.common.models import UserRole

    # Находим пользователей, которые могут управлять to_division
    # Учитываем как явное scope_division, так и автоматическое effective_scope_division
    recipients = []

    if instance.to_division:
        # Находим управление для to_division
        # Поднимаемся по иерархии до level=2 (управление)
        management = instance.to_division
        while management and management.level > 2:
            management = management.parent

        if management and management.level == 2:
            # Собираем управление и его департамент (parent)
            target_divisions = [management]
            if management.parent and management.parent.level == 1:
                target_divisions.append(management.parent)

            # Вариант 1: Пользователи с явно заполненным scope_division
            user_roles_explicit = UserRole.objects.filter(
                scope_division__in=target_divisions
            ).select_related('user')

            # Вариант 2: Пользователи, чей employee.staff_unit.division совпадает с целевыми подразделениями
            # (для случаев, когда scope_division=NULL и используется effective_scope_division)
            from organization_management.apps.employees.models import Employee
            user_roles_implicit = UserRole.objects.filter(
                user__employee__staff_unit__division__in=target_divisions
            ).select_related('user')

            # Объединяем оба набора (используем set для удаления дубликатов)
            recipient_users = set()
            for ur in user_roles_explicit:
                if ur.user:
                    recipient_users.add(ur.user)
            for ur in user_roles_implicit:
                if ur.user:
                    recipient_users.add(ur.user)

            recipients = list(recipient_users)

    # Если не нашли подходящих пользователей, отправляем superuser
    if not recipients:
        superuser = User.objects.filter(is_superuser=True).first()
        if superuser:
            recipients = [superuser]

    # Отправляем уведомление каждому получателю
    employee_name = f"{instance.employee.last_name} {instance.employee.first_name}"

    for recipient in recipients:
        send_notification(
            recipient_id=recipient.id,
            notification_type=Notification.NotificationType.SECONDMENT_REQUEST,
            title=f"Новая заявка на прикомандирование: {employee_name}",
            message=(
                f"Поступила заявка на прикомандирование сотрудника {employee_name} "
                f"из подразделения «{instance.from_division.name}» в ваше подразделение «{instance.to_division.name}». "
                f"Период: {instance.start_date} - {instance.end_date}."
            ),
            link=f"/api/secondments/secondment-requests/{instance.id}/",
            related_object_id=instance.id,
            related_model="SecondmentRequest",
            payload={
                "secondment_request_id": instance.id,
                "employee_id": instance.employee.id,
                "from_division_id": instance.from_division.id,
                "to_division_id": instance.to_division.id,
            },
        )


# ❌ Закомментировано: EmployeeStatusLog не существует в текущей версии
# TODO: Восстановить когда будет создана правильная модель
# @receiver(post_save, sender=EmployeeStatus, dispatch_uid="create_status_update_notification")
# def create_status_update_notification(sender, instance, created, **kwargs):
#     if not created or not instance.employee or not instance.employee.user:
#         return
#
#     Notification.objects.create(
#         recipient=instance.employee.user,
#         notification_type=Notification.NotificationType.STATUS_CHANGED,
#         title=f"Your status has been updated to {instance.get_status_display()}",
#         message=(
#             f'Your status has been updated to "{instance.get_status_display()}" '
#             f"from {instance.start_date}."
#         ),
#         related_object_id=instance.id,
#         related_model="EmployeeStatus",
#         payload={"status_id": instance.id, "new_status": instance.status_type},
#     )


# ✅ Сигнал только на Employee
@receiver(post_save, sender=Employee, dispatch_uid="create_employee_update_notification")
def create_employee_update_notification(sender, instance, created, **kwargs):
    if not instance.user:
        return

    action = "created" if created else "updated"

    Notification.objects.create(
        recipient=instance.user,
        notification_type=Notification.NotificationType.STATUS_CHANGED,
        title=f"Your employee profile has been {action}",
        message=f"Your profile has been {action}.",
        related_object_id=instance.id,
        related_model="Employee",
        payload={"employee_id": instance.id},
    )


# ✅ Сигнал только на Employee
@receiver(post_delete, sender=Employee, dispatch_uid="create_employee_delete_notification")
def create_employee_delete_notification(sender, instance, **kwargs):
    recipients = User.objects.filter(is_superuser=True)
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            notification_type=Notification.NotificationType.STATUS_CHANGED,
            title=f"Employee Deleted: {instance.full_name}",
            message=f"The employee profile for {instance.full_name} has been deleted.",
            related_object_id=instance.id,
            related_model="Employee",
            payload={
                "employee_id": instance.id,
                "full_name": instance.full_name,
            },
        )
