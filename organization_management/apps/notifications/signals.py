"""
Signal handlers for notifications.

These receivers listen to model events across the personnel
application and generate corresponding ``Notification`` records.  When
Channels is installed and properly configured, the receivers also
broadcast real‑time messages over WebSocket so that clients can
immediately reflect state changes without polling.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from organization_management.apps.secondments.models import SecondmentRequest
from organization_management.apps.statuses.models import EmployeeStatusLog
from organization_management.apps.employees.models import Vacancy, Employee
from .models import Notification, NotificationType

# Attempt to import Channels components for real‑time notifications.  If
# Channels is not installed or misconfigured, real‑time delivery will
# gracefully degrade to storing notifications in the database only.
try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    _has_channels = True
except Exception:
    _has_channels = False


@receiver(post_save, sender=SecondmentRequest, dispatch_uid="create_secondment_notification")
def create_secondment_notification(sender, instance, created, **kwargs):
    """
    Notify a recipient when a secondment request is created.

    If the request is not yet approved, the notification is sent to a
    superuser; once approved, the ``approved_by`` field is used.  The
    related object ID is stored for client linking.
    """
    if created:
        recipient = instance.approved_by or User.objects.filter(is_superuser=True).first()
        if recipient:
            Notification.objects.create(
                recipient=recipient,
                notification_type=NotificationType.SECONDMENT,
                title=f"New Secondment Request for {instance.employee.full_name}",
                message=(
                    f"A new secondment from {instance.from_division.name} to "
                    f"{instance.to_division.name} has been requested for {instance.employee.full_name}."
                ),
                related_object_id=instance.id,
                related_model="SecondmentRequest",
                payload={"secondment_request_id": instance.id, "employee_id": instance.employee.id},
            )


@receiver(post_save, sender=EmployeeStatusLog, dispatch_uid="create_status_update_notification")
def create_status_update_notification(sender, instance, created, **kwargs):
    """
    Notify a user when their status has been updated.

    Only logs that have an associated employee user will generate a
    notification.  Real‑time messages are sent over the user's
    personal WebSocket group if Channels is available.
    """
    if created and instance.employee.user:
        Notification.objects.create(
            recipient=instance.employee.user,
            notification_type=NotificationType.STATUS_UPDATE,
            title=f"Your status has been updated to {instance.get_status_display()}",
            message=(
                f'Your status has been updated to "{instance.get_status_display()}" '
                f"from {instance.date_from}."
            ),
            related_object_id=instance.id,
            related_model="EmployeeStatusLog",
            payload={"status_log_id": instance.id, "new_status": instance.status},
        )
        # If real‑time channels are configured, send an immediate update
        if _has_channels:
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{instance.employee.user.id}_notifications",
                    {
                        "type": "notification.message",
                        "message": {
                            "type": "status_update",
                            "employee_id": instance.employee.id,
                            "new_status": instance.status,
                        },
                    },
                )
            except Exception:
                # Do not propagate channel errors
                pass


@receiver(post_save, sender=Vacancy, dispatch_uid="create_vacancy_notification")
def create_vacancy_notification(sender, instance, created, **kwargs):
    """
    Notify the creator of a vacancy when it is created.
    """
    if created and instance.created_by:
        Notification.objects.create(
            recipient=instance.created_by,
            notification_type=NotificationType.VACANCY_CREATED,
            title=f"New Vacancy Created: {instance.title}",
            message=(
                f'A new vacancy "{instance.title}" has been created in '
                f"{instance.staffing_unit.division.name}."
            ),
            related_object_id=instance.id,
            related_model="Vacancy",
            payload={
                "vacancy_id": instance.id,
                "division_id": instance.staffing_unit.division.id,
            },
        )


@receiver(post_save, sender=Employee, dispatch_uid="create_employee_update_notification")
def create_employee_update_notification(sender, instance, created, **kwargs):
    """
    Notify the employee when their profile is created or updated.
    """
    action = "created" if created else "updated"
    if instance.user:
        Notification.objects.create(
            recipient=instance.user,
            notification_type=NotificationType.TRANSFER,
            title=f"Your employee profile has been {action}",
            message=f"Your profile has been {action}.",
            related_object_id=instance.id,
            related_model="Employee",
            payload={"employee_id": instance.id},
        )


@receiver(post_delete, sender=Employee, dispatch_uid="create_employee_delete_notification")
def create_employee_delete_notification(sender, instance, **kwargs):
    """
    Notify superusers when an employee is deleted.
    """
    recipients = User.objects.filter(is_superuser=True)
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            notification_type=NotificationType.TRANSFER,
            title=f"Employee Deleted: {instance.full_name}",
            message=f"The employee profile for {instance.full_name} has been deleted.",
            related_object_id=instance.id,
            related_model="Employee",
            payload={
                "employee_id": instance.id,
                "full_name": instance.full_name,
            },
        )