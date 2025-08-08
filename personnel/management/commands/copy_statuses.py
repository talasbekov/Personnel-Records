"""
Management command to copy employee statuses forward to a new date.

By default this command looks at the current date (``datetime.date.today()``)
and copies the status of each active employee from the previous day.  If a
status has already been manually set for the target date, or if the last
known status is the default ``ON_DUTY_SCHEDULED``, nothing is copied for
that employee.  Copied records are marked with the ``is_auto_copied`` flag
so that subsequent runs can skip them.

An optional ``--target-date`` argument allows the caller to override the
date for which statuses should be copied.  This is particularly useful
for scheduling weekend copies (e.g. copying Friday's statuses to
Saturday and Sunday) from Celery tasks.  The argument expects an ISO
formatted date string (YYYY-MM-DD).  If an invalid date is provided the
command will emit an error and exit gracefully.
"""

import datetime
from django.core.management.base import BaseCommand
from django.db.models import Q
from personnel.models import Employee, EmployeeStatusLog, EmployeeStatusType


class Command(BaseCommand):
    help = (
        "Copies the status of each employee from the previous day to the "
        "target date if no status is set. Use --target-date to specify a "
        "particular date in YYYY-MM-DD format."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-date",
            type=str,
            default=None,
            help="Override the date to copy statuses to (YYYY-MM-DD).",
        )

    def handle(self, *args, **options):
        # Determine the target date for copying.  Accept an override via --target-date.
        target_date_str = options.get("target_date")
        if target_date_str:
            try:
                today = datetime.date.fromisoformat(target_date_str)
            except ValueError:
                self.stderr.write(
                    self.style.ERROR("Invalid --target-date format. Use YYYY-MM-DD.")
                )
                return
        else:
            today = datetime.date.today()

        yesterday = today - datetime.timedelta(days=1)

        self.stdout.write(
            f"Starting status copy for {today.isoformat()} from {yesterday.isoformat()}..."
        )

        # Fetch all active employees once to avoid N queries
        active_employees = Employee.objects.filter(is_active=True)
        copied_count = 0
        skipped_count = 0

        for employee in active_employees:
            # Check if there's already a manually created status for the target date
            has_manual_status_for_today = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=today,
                is_auto_copied=False,
            ).exists()
            if has_manual_status_for_today:
                skipped_count += 1
                continue

            # Find the active status as of yesterday.  We look for the most
            # recent status log whose date range includes yesterday.
            yesterday_status_log = (
                employee.status_logs.filter(date_from__lte=yesterday)
                .filter(Q(date_to__gte=yesterday) | Q(date_to__isnull=True))
                .order_by("-date_from", "-id")
                .first()
            )

            if not yesterday_status_log:
                # No status yesterday implies the default status, so skip copying.
                skipped_count += 1
                continue

            # Do not copy the default "on duty scheduled" status.
            if yesterday_status_log.status == EmployeeStatusType.ON_DUTY_SCHEDULED:
                skipped_count += 1
                continue

            # Check if the existing status log already covers the target date.
            if (
                yesterday_status_log.date_to is None
                or yesterday_status_log.date_to >= today
            ):
                # The log spans the target date; nothing to do.
                skipped_count += 1
                continue

            # Idempotency: If we've already auto copied this particular status for the target date, skip.
            is_already_copied = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from=today,
                status=yesterday_status_log.status,
                is_auto_copied=True,
            ).exists()
            if is_already_copied:
                skipped_count += 1
                continue

            # Create a new single‑day log copying the status forward.
            EmployeeStatusLog.objects.create(
                employee=employee,
                status=yesterday_status_log.status,
                date_from=today,
                date_to=today,
                comment=(
                    f"Auto‑copied from {yesterday.isoformat()}. Original comment: "
                    f"{yesterday_status_log.comment or ''}"
                ),
                secondment_division=yesterday_status_log.secondment_division,
                is_auto_copied=True,
                created_by=None,  # System action
            )
            copied_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed statuses. Copied: {copied_count}, Skipped: {skipped_count}."
            )
        )