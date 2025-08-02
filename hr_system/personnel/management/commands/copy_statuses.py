from django.core.management.base import BaseCommand
from django.db.models import Q
from personnel.models import Employee, EmployeeStatusLog, EmployeeStatusType
import datetime

class Command(BaseCommand):
    help = 'Copies the status of each employee from the previous day to the current day if no status is set.'

    def handle(self, *args, **options):
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        self.stdout.write(f"Starting status copy for {today} from {yesterday}...")

        # Get all active employees
        active_employees = Employee.objects.filter(is_active=True)
        copied_count = 0
        skipped_count = 0

        for employee in active_employees:
            # Check if there's already a status manually set for today
            has_manual_status_for_today = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=today,
                is_auto_copied=False
            ).exists()

            if has_manual_status_for_today:
                skipped_count += 1
                continue

            # Find the active status from yesterday
            yesterday_status_log = employee.status_logs.filter(
                date_from__lte=yesterday
            ).filter(
                Q(date_to__gte=yesterday) | Q(date_to__isnull=True)
            ).order_by('-date_from', '-id').first()

            if not yesterday_status_log:
                # If no status yesterday, they are 'In Line-up' by default, no need to copy.
                skipped_count += 1
                continue

            # If yesterday's status was the default 'In Line-up', no need to create a new record.
            if yesterday_status_log.status == EmployeeStatusType.ON_DUTY_SCHEDULED:
                skipped_count += 1
                continue

            # Check if this exact status log already covers today
            if yesterday_status_log.date_to is None or yesterday_status_log.date_to >= today:
                # The existing log is multi-day and already covers today. Nothing to do.
                skipped_count += 1
                continue

            # This is the most complex case: yesterday was the *last day* of a status.
            # The spec implies we should copy it forward one more day.
            # But a better interpretation is that if a status ends, the user should revert to 'in line-up'.
            # The current task is to "copy statuses". So we will copy a status if it was active yesterday.
            # A simpler logic is to find the status for yesterday, and if it's not "In Line-up",
            # ensure there's a log for today.

            # Idempotency check: Has a log for this status already been copied for today?
            is_already_copied = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=today,
                status=yesterday_status_log.status,
                is_auto_copied=True
            ).exists()

            if is_already_copied:
                skipped_count += 1
                continue

            # --- Create the new copied status log for today ---
            # We create a single-day entry.
            EmployeeStatusLog.objects.create(
                employee=employee,
                status=yesterday_status_log.status,
                date_from=today,
                date_to=today,
                comment=f"Auto-copied from {yesterday}. Original comment: {yesterday_status_log.comment}",
                secondment_division=yesterday_status_log.secondment_division,
                is_auto_copied=True,
                created_by=None # System action
            )
            copied_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully processed statuses. Copied: {copied_count}, Skipped: {skipped_count}.'))
