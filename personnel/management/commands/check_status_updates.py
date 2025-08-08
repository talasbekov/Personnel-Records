"""
Management command to check for overdue status updates and trigger escalations.

This command inspects ``DivisionStatusUpdate`` records to determine whether
each division has updated its statuses for the previous day.  If any
divisions are overdue, escalation notifications are created for all
superusers and corresponding audit log entries are recorded.
"""

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from personnel.models import DivisionStatusUpdate, Division
from notifications.models import Notification, NotificationType
from audit.models import AuditLog


class Command(BaseCommand):
    help = "Checks for divisions with overdue status updates and triggers escalations."

    def handle(self, *args, **options):
        # SLA: statuses must be updated for the previous day.
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        self.stdout.write(f"Checking status updates for {yesterday}...")

        # Determine which divisions were updated for yesterday
        all_divisions = Division.objects.all()
        updated_division_ids = DivisionStatusUpdate.objects.filter(
            update_date=yesterday, is_updated=True
        ).values_list("division_id", flat=True)
        overdue_divisions = all_divisions.exclude(pk__in=updated_division_ids)

        if not overdue_divisions:
            self.stdout.write(self.style.SUCCESS("All divisions are up to date."))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {len(overdue_divisions)} overdue divisions.")
        )

        # Identify recipients for escalation notifications (all superusers)
        recipients = User.objects.filter(is_superuser=True)
        if not recipients.exists():
            self.stderr.write(
                self.style.ERROR(
                    "No superusers found to send escalation notifications."
                )
            )
            return

        for division in overdue_divisions:
            # Create escalation notifications for each recipient
            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    notification_type=NotificationType.ESCALATION,
                    title=f"Escalation: Status update for {division.name} is overdue",
                    message=(
                        f"The status update for the division \"{division.name}\" for {yesterday} has not been completed."
                    ),
                    payload={
                        "division_id": division.id,
                        "overdue_date": str(yesterday),
                    },
                )

            # Create an audit log entry capturing the escalation event
            AuditLog.objects.create(
                action_type="ESCALATION",
                user=None,  # System action
                payload={
                    "message": f"Escalation triggered for division {division.name} for date {yesterday}",
                    "division_id": division.id,
                },
            )
            self.stdout.write(
                f"Escalation triggered for division: {division.name}"
            )

        self.stdout.write(self.style.SUCCESS("Escalation process complete."))