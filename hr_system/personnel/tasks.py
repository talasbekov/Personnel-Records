"""
Celery tasks for the personnel application.

This module defines scheduled tasks for escalation of status updates and
automatic maintenance of employee status logs.  The tasks are designed
to be registered in Celery beat and executed at specific times of day
as described in the technical specification.  Note that actual
notification delivery should be implemented via the project's
notification service (e.g. channels, email); here we include only
placeholders for integration.
"""

import datetime
from django.utils import timezone
from celery import shared_task

from .models import Division, Employee, EmployeeStatusLog, EmployeeStatusType
from django.db import models


@shared_task
def escalation_14_00():
    """Notify Role‑2 users (department heads) about missing status updates.

    This task should run daily at 14:00.  It iterates over divisions
    whose status updates are incomplete for today and sends a reminder
    to the relevant department heads.  The actual delivery mechanism
    (WebSocket, push, email) should be implemented in the notification
    service and injected here.
    """
    today = timezone.now().date()
    # Determine divisions where statuses are not updated today
    from .views import _gather_descendant_ids
    from .models import DivisionStatusUpdate, UserProfile, UserRole
    incomplete_divs = DivisionStatusUpdate.objects.filter(update_date=today, is_updated=False)
    # Group divisions by their parent departments
    for update in incomplete_divs:
        division = update.division
        # Ascend to department level
        current = division
        while current and current.division_type not in [division.DivisionType.DEPARTMENT, division.DivisionType.COMPANY]:
            current = current.parent_division
        if not current or current.division_type != division.DivisionType.DEPARTMENT:
            continue
        # Find users with Role‑2 assigned to this department
        profiles = UserProfile.objects.filter(role=UserRole.ROLE_2, division_assignment=current)
        # TODO: send notification to each user in profiles
        for profile in profiles:
            pass  # integrate with notification service


@shared_task
def escalation_16_00():
    """Notify Role‑4 users (system administrators) about missing updates.

    Runs daily at 16:00.  Similar to ``escalation_14_00`` but targets
    system administrators for broader oversight.  Actual delivery
    integration is deferred to the notification layer.
    """
    today = timezone.now().date()
    from .models import DivisionStatusUpdate, UserProfile, UserRole
    incomplete_divs = DivisionStatusUpdate.objects.filter(update_date=today, is_updated=False)
    admin_profiles = UserProfile.objects.filter(role=UserRole.ROLE_4)
    for profile in admin_profiles:
        # TODO: send a summary notification listing incomplete divisions
        pass


@shared_task
def auto_copy_18_00():
    """Automatically copy employee statuses forward after 18:00.

    This task runs daily at 18:00.  For any division that has not
    updated its statuses for today, the statuses from the previous day
    are copied to ensure continuity.  Newly created logs are marked
    with ``is_auto_copied``.
    """
    today = timezone.now().date()
    yesterday = today - datetime.timedelta(days=1)
    from .models import DivisionStatusUpdate
    divisions_to_copy = DivisionStatusUpdate.objects.filter(update_date=today, is_updated=False).values_list("division_id", flat=True)
    for division_id in divisions_to_copy:
        division = Division.objects.get(id=division_id)
        # Copy statuses for each employee in the division
        employees = Employee.objects.filter(division=division, is_active=True)
        for employee in employees:
            # Find the most recent log covering yesterday
            log = EmployeeStatusLog.objects.filter(employee=employee, date_from__lte=yesterday).filter(
                models.Q(date_to__gte=yesterday) | models.Q(date_to__isnull=True)
            ).order_by("-date_from", "-id").first()
            if log:
                # Copy log forward for today
                EmployeeStatusLog.objects.create(
                    employee=employee,
                    status=log.status,
                    date_from=today,
                    date_to=log.date_to,
                    comment=log.comment,
                    secondment_division=log.secondment_division,
                    created_by=None,
                    is_auto_copied=True,
                )


@shared_task
def auto_revert_expired_statuses():
    """Revert employees to default status when a status period expires.

    This task should run daily (e.g. at midnight).  It looks for
    `EmployeeStatusLog` entries with a defined ``date_to`` that is
    earlier than today and ensures a new log with the default status
    (``ON_DUTY_SCHEDULED``) begins on the day after ``date_to``.
    """
    today = timezone.now().date()
    expired_logs = EmployeeStatusLog.objects.filter(date_to__lt=today)
    for log in expired_logs:
        # Determine the start of the new period
        new_start = log.date_to + datetime.timedelta(days=1)
        # Check if a log already exists covering the new period
        exists = EmployeeStatusLog.objects.filter(
            employee=log.employee,
            date_from__lte=new_start,
        ).filter(
            models.Q(date_to__gte=new_start) | models.Q(date_to__isnull=True)
        ).exists()
        if not exists:
            EmployeeStatusLog.objects.create(
                employee=log.employee,
                status=EmployeeStatusType.ON_DUTY_SCHEDULED,
                date_from=new_start,
                date_to=None,
                comment="Automatically returned to duty",
                created_by=None,
                is_auto_copied=False,
            )