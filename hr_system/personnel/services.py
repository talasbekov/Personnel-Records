"""
Utility functions for the personnel application.

This module contains helper functions to compute statistics for a
division on a given date and to generate simple reports in DOCX, XLSX
and PDF formats.  The implementations here are intentionally
lightweight and designed to satisfy the reporting requirements of the
technical specification without re‑implementing the full document
generation logic of the original system.  They may be expanded or
replaced with more sophisticated templates as needed.
"""

import io
import datetime
from collections import defaultdict
from django.utils import timezone
from docx import Document
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from .models import Division, Employee, EmployeeStatusType
from .models import EmployeeStatusLog, StaffingUnit  # for detailed reports
from django.db.models import Q
from docx.shared import Pt
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT


def _gather_descendants(division):
    """
    Breadth‑first traversal to collect a division and all of its child
    divisions.  Returns a list of ``Division`` instances.
    """
    result = []
    queue = [division]
    while queue:
        current = queue.pop(0)
        result.append(current)
        queue.extend(list(current.child_divisions.all()))
    return result


def get_division_statistics(division, target_date):
    """
    Compute a summary of employee statuses for a division on a given date.

    The summary is a dictionary keyed by ``EmployeeStatusType`` values
    mapping to the number of employees in that status across the
    division and all its descendants.  Statuses not present on that
    date are omitted from the result.

    :param division: The ``Division`` instance to summarise.
    :param target_date: A ``date`` object representing the day of interest.
    :return: A dict mapping status codes to counts.
    """
    stats = defaultdict(int)
    # Gather all employees in the division and its descendants
    all_divisions = _gather_descendants(division)
    employees = Employee.objects.filter(division__in=all_divisions, is_active=True)
    for employee in employees:
        status = employee.get_current_status(date=target_date)
        stats[status] += 1
    return stats


def _build_docx_from_stats(title, stats, date_range=None):
    """
    Create a Word document summarising status counts.

    :param title: Document heading
    :param stats: Dict of status counts
    :param date_range: Optional string describing the date range
    :return: A ``BytesIO`` containing the document content
    """
    doc = Document()
    doc.add_heading(title, level=1)
    if date_range:
        doc.add_paragraph(date_range)
    table = doc.add_table(rows=1 + len(stats), cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Status"
    hdr_cells[1].text = "Count"
    for i, (status, count) in enumerate(stats.items(), start=1):
        row_cells = table.rows[i].cells
        row_cells[0].text = EmployeeStatusType(status).label if status in EmployeeStatusType.values else status
        row_cells[1].text = str(count)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def generate_expense_report_docx(stats):
    """
    Generate a one‑day expense report in DOCX format given statistics.

    ``stats`` should be a dict produced by ``get_division_statistics``.
    """
    return _build_docx_from_stats("Daily Expense Report", stats)


def generate_periodic_report_docx(division, date_from, date_to):
    """
    Generate a multi‑day expense report in DOCX format for a date range.
    Computes statistics for each day in the range and aggregates them.
    """
    # Aggregate counts across the date range
    aggregated = defaultdict(int)
    current = date_from
    while current <= date_to:
        daily_stats = get_division_statistics(division, current)
        for status, count in daily_stats.items():
            aggregated[status] += count
        current += datetime.timedelta(days=1)
    title = "Periodic Expense Report"
    date_range = f"Period: {date_from.isoformat()} to {date_to.isoformat()}"
    return _build_docx_from_stats(title, aggregated, date_range=date_range)

# ---------------------------------------------------------------------------
# Detailed report generation
# ---------------------------------------------------------------------------

def _collect_status_details(division, start_date, end_date):
    """
    Collect detailed status information for all employees in ``division`` and
    its descendants between ``start_date`` and ``end_date`` inclusive.

    Returns a dictionary keyed by status code.  Each value is a list of
    dictionaries with keys ``name``, ``comment`` and ``period``.
    """
    descendants = _gather_descendants(division)
    employees = Employee.objects.filter(division__in=descendants, is_active=True)
    details = defaultdict(list)
    # Normalize dates
    if end_date is None:
        end_date = start_date
    for emp in employees:
        # find logs that intersect the period
        logs = EmployeeStatusLog.objects.filter(
            employee=emp,
            date_from__lte=end_date,
        ).filter(Q(date_to__gte=start_date) | Q(date_to__isnull=True)).order_by("-date_from", "-id")
        if logs.exists():
            # use the log(s) to determine the statuses during the period
            for log in logs:
                # Determine the intersection of [log.date_from, log.date_to] and [start_date, end_date]
                period_start = max(log.date_from, start_date)
                period_end = min(log.date_to or end_date, end_date)
                period_str = (
                    f"{period_start.isoformat()} – {period_end.isoformat()}"
                    if period_start != period_end
                    else period_start.isoformat()
                )
                details[log.status].append(
                    {
                        "name": emp.full_name,
                        "comment": log.comment or "",
                        "period": period_str,
                    }
                )
        else:
            # No log means default status for the whole period
            period_str = (
                f"{start_date.isoformat()} – {end_date.isoformat()}"
                if start_date != end_date
                else start_date.isoformat()
            )
            details[EmployeeStatusType.ON_DUTY_SCHEDULED].append(
                {
                    "name": emp.full_name,
                    "comment": "",
                    "period": period_str,
                }
            )
    return details


def generate_detailed_report_docx(division, date_from, date_to=None):
    """
    Generate a detailed personnel report in DOCX format.

    The report includes a header in Kazakh, a table listing each
    recognised status with four columns (count, names, comments, date
    ranges) and a final row summarising the staffing situation.  The
    document is landscape‑oriented and uses 16pt font for the header
    and 8pt font for table contents.

    :param division: Division for which to generate the report.
    :param date_from: Start date of the report period (date).
    :param date_to: End date of the report period (date).  If None,
      defaults to ``date_from``.
    :returns: BytesIO containing the DOCX data.
    """
    if date_to is None:
        date_to = date_from
    # Collect status details
    details = _collect_status_details(division, date_from, date_to)
    # Compute staffing numbers
    descendants = _gather_descendants(division)
    staffing_units = StaffingUnit.objects.filter(division__in=descendants)
    authorised_count = sum(unit.quantity for unit in staffing_units)
    employees = Employee.objects.filter(division__in=descendants, is_active=True)
    active_count = employees.count()
    vacancies = max(authorised_count - active_count, 0)
    # Create document
    doc = Document()
    # Landscape orientation
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    # Header
    date_str = date_from.isoformat() if date_from == date_to else f"{date_from.isoformat()} – {date_to.isoformat()}"
    title = f"{division.name} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ {date_str} ЖЫЛҒЫ"
    p = doc.add_paragraph()
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(16)
    doc.add_paragraph()  # blank line
    # Build table with statuses and summary row
    statuses = [
        EmployeeStatusType.ON_DUTY_SCHEDULED,
        EmployeeStatusType.ON_DUTY_ACTUAL,
        EmployeeStatusType.AFTER_DUTY,
        EmployeeStatusType.BUSINESS_TRIP,
        EmployeeStatusType.TRAINING_ETC,
        EmployeeStatusType.ON_LEAVE,
        EmployeeStatusType.SICK_LEAVE,
        EmployeeStatusType.SECONDED_OUT,
        EmployeeStatusType.SECONDED_IN,
    ]
    table = doc.add_table(rows=1 + len(statuses) + 1, cols=5)
    table.style = "Table Grid"
    header_cells = table.rows[0].cells
    headers = ["Статус", "Количество", "ФИО", "Комментарий", "Даты"]
    for idx, text in enumerate(headers):
        header_cells[idx].text = text
    # Fill rows
    for i, status in enumerate(statuses, start=1):
        row = table.rows[i].cells
        row[0].text = EmployeeStatusType(status).label
        items = details.get(status, [])
        row[1].text = str(len(items))
        row[2].text = ", ".join(item["name"] for item in items)
        row[3].text = "; ".join(item["comment"] for item in items if item["comment"]) or ""
        row[4].text = "; ".join(item["period"] for item in items if item["period"]) or ""
    # Summary row
    summary = table.rows[len(statuses) + 1].cells
    summary[0].text = "Штат"
    summary[1].text = str(authorised_count)
    summary[2].text = f"По списку: {active_count}; Вакантные: {vacancies}"
    summary[3].text = "Штат = По списку + Вакантные"
    summary[4].text = ""
    # Set font size for all table text to 8pt
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)
    # Return buffer
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def generate_detailed_periodic_report_docx(division, date_from, date_to):
    """
    Generate a detailed report for a date range.

    This aggregates status details across the period and merges periods
    where possible.  The table layout is the same as for the daily
    detailed report.  The header contains the date range.
    """
    return generate_detailed_report_docx(division, date_from, date_to)


def _build_xlsx_from_stats(title, stats, date_range=None):
    """
    Create an Excel workbook summarising status counts.
    Returns a BytesIO containing the workbook data.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]  # Worksheet title max length 31 chars
    row_idx = 1
    if date_range:
        ws.cell(row=row_idx, column=1, value=date_range)
        row_idx += 1
    ws.cell(row=row_idx, column=1, value="Status")
    ws.cell(row=row_idx, column=2, value="Count")
    row_idx += 1
    for status, count in stats.items():
        ws.cell(row=row_idx, column=1, value=EmployeeStatusType(status).label if status in EmployeeStatusType.values else status)
        ws.cell(row=row_idx, column=2, value=count)
        row_idx += 1
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_expense_report_xlsx(stats):
    """Generate a one‑day expense report in XLSX format."""
    return _build_xlsx_from_stats("Daily Expense Report", stats)


def generate_periodic_report_xlsx(division, date_from, date_to):
    """Generate a multi‑day expense report in XLSX format."""
    aggregated = defaultdict(int)
    current = date_from
    while current <= date_to:
        daily_stats = get_division_statistics(division, current)
        for status, count in daily_stats.items():
            aggregated[status] += count
        current += datetime.timedelta(days=1)
    title = "Periodic Expense Report"
    date_range = f"Period: {date_from.isoformat()} to {date_to.isoformat()}"
    return _build_xlsx_from_stats(title, aggregated, date_range=date_range)


def _build_pdf_from_stats(title, stats, date_range=None):
    """
    Create a PDF document summarising status counts.

    Uses ReportLab to construct a simple table.  Returns a BytesIO with
    the PDF data.
    """
    buffer = io.BytesIO()
    # Use a landscape orientation for more space
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    style_sheet = getSampleStyleSheet()
    elements.append(Paragraph(title, style_sheet["Title"]))
    if date_range:
        elements.append(Paragraph(date_range, style_sheet["Normal"]))
    # Build data rows
    data = [["Status", "Count"]]
    for status, count in stats.items():
        data.append([
            EmployeeStatusType(status).label if status in EmployeeStatusType.values else status,
            str(count),
        ])
    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_expense_report_pdf(stats):
    """Generate a one‑day expense report in PDF format."""
    return _build_pdf_from_stats("Daily Expense Report", stats)


def generate_periodic_report_pdf(division, date_from, date_to):
    """Generate a multi‑day expense report in PDF format."""
    aggregated = defaultdict(int)
    current = date_from
    while current <= date_to:
        daily_stats = get_division_statistics(division, current)
        for status, count in daily_stats.items():
            aggregated[status] += count
        current += datetime.timedelta(days=1)
    title = "Periodic Expense Report"
    date_range = f"Period: {date_from.isoformat()} to {date_to.isoformat()}"
    return _build_pdf_from_stats(title, aggregated, date_range=date_range)