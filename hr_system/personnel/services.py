from collections import defaultdict
from django.db.models import Sum, Q
from django.db import models
from .models import Division, Employee, StaffingUnit, SecondmentRequest, EmployeeStatusType
import datetime

def get_division_statistics(division: Division, on_date: datetime.date):
    """
    Calculates personnel statistics for a given division on a specific date.

    Args:
        division: The Division object to calculate statistics for.
        on_date: The date for which to calculate the statistics.

    Returns:
        A dictionary containing all the calculated statistics.
    """
    # --- Step 1: Get all child divisions to include in the calculation ---
    # For now, we assume calculations are for the division and its children.
    # This could be parameterized later.
    all_division_ids = [division.id]
    queue = [division]
    visited = {division.id}
    while queue:
        current_division = queue.pop(0)
        for child in current_division.child_divisions.all():
            if child.id not in visited:
                all_division_ids.append(child.id)
                visited.add(child.id)
                queue.append(child)

    # --- Step 2: Calculate Staffing, On List, and Vacant ---
    # Штат (Total Staffing)
    total_staffing = StaffingUnit.objects.filter(
        division_id__in=all_division_ids
    ).aggregate(total=Sum('quantity'))['total'] or 0

    # По списку (On List) - Employees whose home division is in the scope
    employees_on_list = Employee.objects.filter(
        division_id__in=all_division_ids,
        is_active=True,
        hired_date__lte=on_date
    ).exclude(
        fired_date__lte=on_date
    )
    on_list_count = employees_on_list.count()

    # Вакантные (Vacant)
    vacant_count = total_staffing - on_list_count

    # --- Step 3: Calculate status breakdown for employees on the list ---
    status_counts = defaultdict(int)
    status_details = defaultdict(list)

    for emp in employees_on_list:
        status = emp.get_current_status(date=on_date)
        status_counts[status] += 1

        # Prepare details for the report (name, comment, dates)
        log_entry = emp.status_logs.filter(
            date_from__lte=on_date,
            status=status
        ).filter(
            models.Q(date_to__gte=on_date) | models.Q(date_to__isnull=True)
        ).order_by('-date_from', '-id').first()

        details = {
            'full_name': emp.full_name,
            'comment': log_entry.comment if log_entry else '',
            'date_from': log_entry.date_from if log_entry else None,
            'date_to': log_entry.date_to if log_entry else None,
        }
        status_details[status].append(details)

    # В строю (In Line-up)
    in_lineup_count = status_counts[EmployeeStatusType.ON_DUTY_SCHEDULED]

    # --- Step 4: Calculate Seconded-in employees (+N) ---
    # Employees seconded INTO this division on the given date
    seconded_in_requests = SecondmentRequest.objects.filter(
        to_division_id__in=all_division_ids,
        status='APPROVED',
        date_from__lte=on_date
    ).filter(
        models.Q(date_to__gte=on_date) | models.Q(date_to__isnull=True)
    )
    seconded_in_count = seconded_in_requests.count()

    # Also get the status breakdown for these seconded-in employees
    seconded_in_status_counts = defaultdict(int)
    for req in seconded_in_requests:
        status = req.employee.get_current_status(date=on_date)
        seconded_in_status_counts[status] += 1


    # --- Step 5: Assemble the final statistics object ---
    stats = {
        'division_name': division.name,
        'on_date': on_date,
        'total_staffing': total_staffing,
        'on_list_count': on_list_count,
        'vacant_count': vacant_count,
        'in_lineup_count': in_lineup_count,
        'seconded_in_count': seconded_in_count,
        'status_counts': dict(status_counts),
        'seconded_in_status_counts': dict(seconded_in_status_counts),
        'status_details': dict(status_details),
    }

    # Verify the formulas from the spec
    # По списку = В строю + (all other statuses except seconded_out)
    # Note: get_current_status for an employee on the list will never be SECONDED_IN
    on_list_check = sum(v for k, v in status_counts.items())
    assert on_list_count == on_list_check

    # В строю = По списку - (all non-lineup statuses)
    non_lineup_sum = sum(v for k, v in status_counts.items() if k != EmployeeStatusType.ON_DUTY_SCHEDULED)
    in_lineup_check = on_list_count - non_lineup_sum
    assert in_lineup_count == in_lineup_check

    return stats
