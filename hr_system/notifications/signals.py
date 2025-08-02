from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from personnel.models import SecondmentRequest, EmployeeStatusLog, Vacancy, Employee
from .models import Notification, NotificationType
from django.contrib.auth.models import User

# Optional real-time updates via Channels; safe fallback if not installed
try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    _has_channels = True
except ImportError:
    _has_channels = False


@receiver(post_save, sender=SecondmentRequest, dispatch_uid="create_secondment_notification")
def create_secondment_notification(sender, instance, created, **kwargs):
    if created:
        recipient = instance.approved_by or User.objects.filter(is_superuser=True).first()
        if recipient:
            Notification.objects.create(
                recipient=recipient,
                notification_type=NotificationType.SECONDMENT,
                title=f'New Secondment Request for {instance.employee.full_name}',
                message=(
                    f'A new secondment from {instance.from_division.name} to '
                    f'{instance.to_division.name} has been requested for {instance.employee.full_name}.'
                ),
                related_object_id=instance.id,
                related_model='SecondmentRequest',
                payload={'secondment_request_id': instance.id, 'employee_id': instance.employee.id}
            )


@receiver(post_save, sender=EmployeeStatusLog, dispatch_uid="create_status_update_notification")
def create_status_update_notification(sender, instance, created, **kwargs):
    if created and instance.employee.user:
        Notification.objects.create(
            recipient=instance.employee.user,
            notification_type=NotificationType.STATUS_UPDATE,
            title=f'Your status has been updated to {instance.get_status_display()}',
            message=(
                f'Your status has been updated to "{instance.get_status_display()}" '
                f'from {instance.date_from}.'
            ),
            related_object_id=instance.id,
            related_model='EmployeeStatusLog',
            payload={'status_log_id': instance.id, 'new_status': instance.status}
        )

        if _has_channels:
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'user_{instance.employee.user.id}_notifications',
                    {
                        'type': 'notification.message',
                        'message': {
                            'type': 'status_update',
                            'employee_id': instance.employee.id,
                            'new_status': instance.status,
                        },
                    },
                )
            except Exception:
                # Silently ignore if real-time delivery fails
                pass


@receiver(post_save, sender=Vacancy, dispatch_uid="create_vacancy_notification")
def create_vacancy_notification(sender, instance, created, **kwargs):
    if created and instance.created_by:
        Notification.objects.create(
            recipient=instance.created_by,
            notification_type=NotificationType.VACANCY_CREATED,
            title=f'New Vacancy Created: {instance.title}',
            message=(
                f'A new vacancy "{instance.title}" has been created in '
                f'{instance.staffing_unit.division.name}.'
            ),
            related_object_id=instance.id,
            related_model='Vacancy',
            payload={'vacancy_id': instance.id, 'division_id': instance.staffing_unit.division.id}
        )


@receiver(post_save, sender=Employee, dispatch_uid="create_employee_update_notification")
def create_employee_update_notification(sender, instance, created, **kwargs):
    action = "created" if created else "updated"
    if instance.user:
        Notification.objects.create(
            recipient=instance.user,
            notification_type=NotificationType.TRANSFER,
            title=f'Your employee profile has been {action}',
            message=f'Your profile has been {action}.',
            related_object_id=instance.id,
            related_model='Employee',
            payload={'employee_id': instance.id}
        )


@receiver(post_delete, sender=Employee, dispatch_uid="create_employee_delete_notification")
def create_employee_delete_notification(sender, instance, **kwargs):
    recipients = User.objects.filter(is_superuser=True)
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            notification_type=NotificationType.TRANSFER,
            title=f'Employee Deleted: {instance.full_name}',
            message=f'The employee profile for {instance.full_name} has been deleted.',
            related_object_id=instance.id,
            related_model='Employee',
            payload={'employee_id': instance.id, 'full_name': instance.full_name}
        )
