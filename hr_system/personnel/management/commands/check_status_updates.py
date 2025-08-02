from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime
from personnel.models import DivisionStatusUpdate, Division
from notifications.models import Notification, NotificationType
from audit.models import AuditLog
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Checks for divisions with overdue status updates and triggers escalations.'

    def handle(self, *args, **options):
        # SLA: Statuses must be updated for the previous day.
        # We run this command on the next day.
        yesterday = timezone.now().date() - datetime.timedelta(days=1)

        self.stdout.write(f'Checking status updates for {yesterday}...')

        # Get all divisions that should have been updated.
        all_divisions = Division.objects.all()

        # Get all divisions that were updated.
        updated_divisions_pks = DivisionStatusUpdate.objects.filter(
            update_date=yesterday,
            is_updated=True
        ).values_list('division_id', flat=True)

        overdue_divisions = all_divisions.exclude(pk__in=updated_divisions_pks)

        if not overdue_divisions:
            self.stdout.write(self.style.SUCCESS('All divisions are up to date.'))
            return

        self.stdout.write(self.style.WARNING(f'Found {len(overdue_divisions)} overdue divisions.'))

        # Get recipients for escalation notifications (e.g., superusers)
        recipients = User.objects.filter(is_superuser=True)
        if not recipients.exists():
            self.stderr.write(self.style.ERROR('No superusers found to send escalation notifications.'))
            return

        for division in overdue_divisions:
            # Create an escalation notification
            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    notification_type=NotificationType.ESCALATION,
                    title=f'Escalation: Status update for {division.name} is overdue',
                    message=f'The status update for the division "{division.name}" for {yesterday} has not been completed.',
                    payload={'division_id': division.id, 'overdue_date': str(yesterday)}
                )

            # Create an audit log entry
            AuditLog.objects.create(
                action_type='ESCALATION',
                user=None, # System action
                payload={
                    'message': f'Escalation triggered for division {division.name} for date {yesterday}',
                    'division_id': division.id,
                }
            )
            self.stdout.write(f'Escalation triggered for division: {division.name}')

        self.stdout.write(self.style.SUCCESS('Escalation process complete.'))
