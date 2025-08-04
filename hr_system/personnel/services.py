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