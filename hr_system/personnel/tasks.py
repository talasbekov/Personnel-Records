"""
Celery tasks for the personnel application.

These tasks are responsible for executing periodic maintenance jobs
defined by the technical specification.  They leverage Django's
``call_command`` utility to run management commands within the context
of a Celery worker.  Scheduled execution is configured via
``CELERY_BEAT_SCHEDULE`` in ``hr_system.settings``.

Current tasks:

* ``copy_statuses_task`` – Copies employee statuses from the previous day
  into the target date.  On Mondays this task also backfills statuses
  for Saturday and Sunday in case the scheduler was inactive over the
  weekend.  See ``copy_statuses`` management command for details.

* ``check_status_updates_task`` – Checks for overdue status updates from
  divisions and triggers escalation notifications if necessary.  This
  corresponds to the ``check_status_updates`` management command.
"""

import datetime
from django.utils import timezone
from django.core.management import call_command
from celery import shared_task
from django.db import models


@shared_task
def copy_statuses_task():
    """
    Copy employee statuses forward.  Runs daily shortly after midnight.

    On Mondays the scheduler may need to backfill statuses for the
    weekend.  This task detects a Monday and invokes the underlying
    management command for Saturday and Sunday explicitly using the
    ``target_date`` argument.  For all other days it simply copies
    statuses for today.
    """
    today = timezone.now().date()
    # Monday is weekday 0
    if today.weekday() == 0:
        # Backfill Saturday (two days ago) and Sunday (yesterday)
        for delta in (2, 1):
            target_date = today - datetime.timedelta(days=delta)
            call_command("copy_statuses", target_date=target_date.isoformat())
    # Always copy statuses for today
    call_command("copy_statuses", target_date=today.isoformat())


@shared_task
def check_status_updates_task():
    """
    Task wrapper for the ``check_status_updates`` management command.

    Executed periodically to ensure timely escalation of overdue
    divisions.  The exact schedule is defined by ``CELERY_BEAT_SCHEDULE``.
    """
    call_command("check_status_updates")


@shared_task
def reset_default_statuses_task():
    """
    Automatically reset employees to the default status once a status
    period expires.  This task runs daily and examines the latest
    status log for each employee.  If the latest log has an end date
    strictly before today, a new log with status
    ``EmployeeStatusType.ON_DUTY_SCHEDULED`` is created starting the
    day after the end date.  Comments are set to indicate that the
    reset was automatic.
    """
    from .models import Employee, EmployeeStatusLog, EmployeeStatusType  # local import to avoid circular
    today = timezone.now().date()
    for employee in Employee.objects.all():
        log = employee.status_logs.order_by("-date_from", "-id").first()
        if log and log.date_to and log.date_to < today:
            next_day = log.date_to + datetime.timedelta(days=1)
            # Only create a new log if there isn't already an overlapping log
            existing = employee.status_logs.filter(date_from__lte=next_day).filter(
                models.Q(date_to__gte=next_day) | models.Q(date_to__isnull=True)
            ).exists()
            if not existing:
                EmployeeStatusLog.objects.create(
                    employee=employee,
                    status=EmployeeStatusType.ON_DUTY_SCHEDULED,
                    date_from=next_day,
                    date_to=None,
                    comment="Auto reset to default status",
                    created_by=None,
                )