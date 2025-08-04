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