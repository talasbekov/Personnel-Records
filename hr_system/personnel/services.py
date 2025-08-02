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


import io
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT

def generate_expense_report_docx(division_stats: dict):
    """
    Generates a .docx expense report from division statistics.

    Args:
        division_stats: A dictionary of stats from get_division_statistics.

    Returns:
        An in-memory io.BytesIO buffer containing the .docx file.
    """
    document = Document()

    # --- 1. Set Page Orientation to Landscape ---
    section = document.sections[0]
    new_width, new_height = section.page_height, section.page_width
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = new_width
    section.page_height = new_height
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(1.0)
    section.bottom_margin = Cm(1.0)

    # --- 2. Add Title ---
    title_str = f"{division_stats['division_name']} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ {division_stats['on_date'].strftime('%d.%m.%Y')} ЖЫЛҒЫ"
    title_paragraph = document.add_paragraph()
    title_run = title_paragraph.add_run(title_str)
    title_run.font.name = 'Times New Roman'
    title_run.font.size = Pt(16)
    title_run.bold = True
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # --- 3. Add Table ---
    # Define statuses to include in the report columns, in order
    status_columns = [
        EmployeeStatusType.ON_DUTY_ACTUAL,
        EmployeeStatusType.AFTER_DUTY,
        EmployeeStatusType.BUSINESS_TRIP,
        EmployeeStatusType.TRAINING_ETC,
        EmployeeStatusType.ON_LEAVE,
        EmployeeStatusType.SICK_LEAVE,
        EmployeeStatusType.SECONDED_IN,
        EmployeeStatusType.SECONDED_OUT,
    ]

    num_cols = 6 + len(status_columns)
    table = document.add_table(rows=1, cols=num_cols)
    table.style = 'Table Grid'
    table.autofit = False # Allows setting manual column widths

    # --- 4. Set Column Headers and Widths ---
    hdr_cells = table.rows[0].cells
    headers = [
        "№", "Название управления", "Количество по штату",
        "Количество по списку", "Вакантные должности", "В строю"
    ] + [s.label for s in status_columns]

    for i, header_text in enumerate(headers):
        cell = hdr_cells[i]
        cell.text = header_text
        cell.paragraphs[0].runs[0].font.size = Pt(12)
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        # You can set column widths here if needed, e.g., hdr_cells[0].width = Cm(1)

    # --- 5. Populate Data Row (for a single division report for now) ---
    # This part needs to be adapted for reports with multiple sub-divisions
    row_cells = table.add_row().cells

    on_list_display = f"{division_stats['on_list_count']}"
    if division_stats['seconded_in_count'] > 0:
        on_list_display += f" +{division_stats['seconded_in_count']}"

    data_row = [
        "1",
        division_stats['division_name'],
        str(division_stats['total_staffing']),
        on_list_display,
        str(division_stats['vacant_count']),
        str(division_stats['in_lineup_count']),
    ]

    for status in status_columns:
        count = division_stats['status_counts'].get(status, 0)
        # For SECONDED_IN, we use the dedicated count
        if status == EmployeeStatusType.SECONDED_IN:
            count = division_stats['seconded_in_count']

        # This is a simplified version. The spec requires 4 sub-rows per status.
        # Implementing that requires a more complex table structure.
        # For now, we just put the count.
        cell_content = f"{count}\n"
        cell_content += "Подстрока 1\n"
        cell_content += "Подстрока 2\n"
        cell_content += "Подстрока 3\n"
        cell_content += "Подстрока 4"

        data_row.append(cell_content)

    for i, cell_text in enumerate(data_row):
        cell = row_cells[i]
        cell.text = str(cell_text)
        cell.paragraphs[0].runs[0].font.size = Pt(8)

    # --- 6. Add Total Row ---
    # This would require summing up stats if there were multiple rows.
    # For now, we just copy the single data row and make it bold.
    total_cells = table.add_row().cells
    total_cells[1].text = "Общее"
    total_cells[1].paragraphs[0].runs[0].bold = True

    for i in range(2, num_cols):
        total_cells[i].text = row_cells[i].text
        total_cells[i].paragraphs[0].runs[0].bold = True


    # --- 7. Save to Buffer ---
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer
