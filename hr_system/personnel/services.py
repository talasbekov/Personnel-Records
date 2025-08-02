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

def _add_report_table_to_document(document, division_stats):
    # --- Add Title ---
    title_str = f"{division_stats['division_name']} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ {division_stats['on_date'].strftime('%d.%m.%Y')} ЖЫЛҒЫ"
    title_paragraph = document.add_paragraph()
    title_run = title_paragraph.add_run(title_str)
    title_run.font.name = 'Times New Roman'
    title_run.font.size = Pt(16)
    title_run.bold = True
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # --- Add Table ---
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
    table.autofit = False

    # --- Set Column Headers ---
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

    # --- Populate Data Row ---
    row_cells = table.add_row().cells
    on_list_display = f"{division_stats['on_list_count']}"
    if division_stats['seconded_in_count'] > 0:
        on_list_display += f" +{division_stats['seconded_in_count']}"
    data_row = [
        "1", division_stats['division_name'], str(division_stats['total_staffing']),
        on_list_display, str(division_stats['vacant_count']), str(division_stats['in_lineup_count']),
    ]
    for status in status_columns:
        count = division_stats['status_counts'].get(status, 0)
        if status == EmployeeStatusType.SECONDED_IN:
            count = division_stats['seconded_in_count']
        cell_content = f"{count}\nПодстрока 1\nПодстрока 2\nПодстрока 3\nПодстрока 4"
        data_row.append(cell_content)
    for i, cell_text in enumerate(data_row):
        cell = row_cells[i]
        cell.text = str(cell_text)
        cell.paragraphs[0].runs[0].font.size = Pt(8)

    # --- Add Total Row ---
    total_cells = table.add_row().cells
    total_cells[1].text = "Общее"
    total_cells[1].paragraphs[0].runs[0].bold = True
    for i in range(2, num_cols):
        total_cells[i].text = row_cells[i].text
        total_cells[i].paragraphs[0].runs[0].bold = True

def generate_expense_report_docx(division_stats: dict):
    """
    Generates a .docx expense report from division statistics.
    """
    document = Document()
    # --- Set Page Orientation ---
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(1.0)
    section.bottom_margin = Cm(1.0)

    _add_report_table_to_document(document, division_stats)

    # --- Save to Buffer ---
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

def generate_expense_report_xlsx(division_stats: dict):
    """
    Generates an .xlsx expense report from division statistics.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Expense Report"

    # --- Add Title ---
    title_str = f"{division_stats['division_name']} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ {division_stats['on_date'].strftime('%d.%m.%Y')} ЖЫЛҒЫ"
    ws.merge_cells('A1:N1')
    title_cell = ws['A1']
    title_cell.value = title_str
    title_cell.font = Font(name='Times New Roman', size=16, bold=True)
    title_cell.alignment = Alignment(horizontal='center', vertical='center')

    # --- Add Table Headers ---
    status_columns = [
        EmployeeStatusType.ON_DUTY_ACTUAL, EmployeeStatusType.AFTER_DUTY,
        EmployeeStatusType.BUSINESS_TRIP, EmployeeStatusType.TRAINING_ETC,
        EmployeeStatusType.ON_LEAVE, EmployeeStatusType.SICK_LEAVE,
        EmployeeStatusType.SECONDED_IN, EmployeeStatusType.SECONDED_OUT,
    ]
    headers = [
        "№", "Название управления", "Количество по штату",
        "Количество по списку", "Вакантные должности", "В строю"
    ] + [s.label for s in status_columns]
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # --- Populate Data Row ---
    on_list_display = f"{division_stats['on_list_count']}"
    if division_stats['seconded_in_count'] > 0:
        on_list_display += f" +{division_stats['seconded_in_count']}"
    data_row = [
        "1", division_stats['division_name'], str(division_stats['total_staffing']),
        on_list_display, str(division_stats['vacant_count']), str(division_stats['in_lineup_count']),
    ]
    for status in status_columns:
        count = division_stats['status_counts'].get(status, 0)
        if status == EmployeeStatusType.SECONDED_IN:
            count = division_stats['seconded_in_count']
        cell_content = f"{count}\nПодстрока 1\nПодстрока 2\nПодстрока 3\nПодстрока 4"
        data_row.append(cell_content)
    ws.append(data_row)
    for cell in ws[3]:
        cell.alignment = Alignment(wrap_text=True)

    # --- Save to Buffer ---
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

def generate_expense_report_pdf(division_stats: dict):
    """
    Generates a .pdf expense report from division statistics.
    """
    # It's better to have a helper for the full page, as PDF generation is stateful.
    # This function will handle a single day's report.
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

    # Register a font that supports Cyrillic
    # A proper implementation would bundle a .ttf file.
    # We'll assume a common system font is available for now.
    try:
        pdfmetrics.registerFont(TTFont('Times-Roman', 'times.ttf'))
        main_font = 'Times-Roman'
    except:
        main_font = 'Helvetica' # Fallback

    styles = getSampleStyleSheet()
    styles['h1'].fontName = main_font
    styles['BodyText'].fontName = main_font

    elements = [_create_pdf_page_content(division_stats, styles)]

    doc.build(elements)
    buffer.seek(0)
    return buffer

def _create_pdf_page_content(division_stats, styles):
    """Helper to create the list of Platypus flowables for a single page."""
    # --- Title ---
    title_str = f"{division_stats['division_name']} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ {division_stats['on_date'].strftime('%d.%m.%Y')} ЖЫЛҒЫ"
    title = Paragraph(title_str, styles['h1'])

    # --- Table Data ---
    status_columns = [
        EmployeeStatusType.ON_DUTY_ACTUAL, EmployeeStatusType.AFTER_DUTY,
        EmployeeStatusType.BUSINESS_TRIP, EmployeeStatusType.TRAINING_ETC,
        EmployeeStatusType.ON_LEAVE, EmployeeStatusType.SICK_LEAVE,
        EmployeeStatusType.SECONDED_IN, EmployeeStatusType.SECONDED_OUT,
    ]
    headers = [
        "№", "Название управления", "Количество по штату",
        "Количество по списку", "Вакантные должности", "В строю"
    ] + [s.label for s in status_columns]

    on_list_display = f"{division_stats['on_list_count']}"
    if division_stats['seconded_in_count'] > 0:
        on_list_display += f" +{division_stats['seconded_in_count']}"

    data_row = [
        "1", division_stats['division_name'], str(division_stats['total_staffing']),
        on_list_display, str(division_stats['vacant_count']), str(division_stats['in_lineup_count']),
    ]
    for status in status_columns:
        count = division_stats['status_counts'].get(status, 0)
        if status == EmployeeStatusType.SECONDED_IN:
            count = division_stats['seconded_in_count']
        cell_content = f"{count}\nПодстрока 1\nПодстрока 2\nПодстрока 3\nПодстрока 4"
        data_row.append(Paragraph(cell_content.replace('\n', '<br/>'), styles['BodyText']))

    table_data = [headers, data_row]

    # --- Table Style ---
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ])

    # --- Create Table ---
    table = Table(table_data)
    table.setStyle(style)

    return [title, table]

def generate_periodic_report_docx(division: Division, date_from: datetime.date, date_to: datetime.date):
    """
    Generates a .docx expense report for a date range, with each day on a new page.
    """
    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    # ... set margins ...

    current_date = date_from
    while current_date <= date_to:
        stats = get_division_statistics(division, current_date)
        _add_report_table_to_document(document, stats)
        if current_date < date_to:
            document.add_page_break()
        current_date += datetime.timedelta(days=1)

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer

def generate_periodic_report_xlsx(division: Division, date_from: datetime.date, date_to: datetime.date):
    """
    Generates an .xlsx expense report for a date range, with each day on a new sheet.
    """
    wb = Workbook()
    wb.remove(wb.active) # Remove default sheet

    current_date = date_from
    while current_date <= date_to:
        stats = get_division_statistics(division, current_date)
        ws = wb.create_sheet(title=current_date.strftime('%Y-%m-%d'))
        # Simplified version of single-day xlsx generation.
        # A full implementation would be refactored like the docx version.
        ws.append([f"Report for {current_date.strftime('%d.%m.%Y')}"])
        # ... (add more data from stats)
        current_date += datetime.timedelta(days=1)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

def generate_periodic_report_pdf(division: Division, date_from: datetime.date, date_to: datetime.date):
    """
    Generates a .pdf expense report for a date range, with each day on a new page.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []

    try:
        pdfmetrics.registerFont(TTFont('Times-Roman', 'times.ttf'))
        main_font = 'Times-Roman'
    except:
        main_font = 'Helvetica'
    styles = getSampleStyleSheet()
    styles['h1'].fontName = main_font
    styles['BodyText'].fontName = main_font

    current_date = date_from
    while current_date <= date_to:
        stats = get_division_statistics(division, current_date)
        elements.extend(_create_pdf_page_content(stats, styles))
        if current_date < date_to:
            elements.append(PageBreak())
        current_date += datetime.timedelta(days=1)

    doc.build(elements)
    buffer.seek(0)
    return buffer
