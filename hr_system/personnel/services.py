"""
Enhanced utility functions for the personnel application.

This module extends the basic reporting helpers with a more detailed
document generator that conforms to the formatting requirements of the
technical specification.  In particular, it implements a daily
personnel lineup document (``generate_detailed_report_docx``) that
organises employee data by status and presents counts, names,
comments and dates in a tabular layout.

The function can be dropped into the existing ``services.py`` in the
original repository; it relies only on models defined in the
``personnel`` app and on the ``python‑docx`` package.
"""

import io
import datetime
from collections import defaultdict
from django.utils import timezone
from docx import Document

from .models import Division, Employee, EmployeeStatusType, StaffingUnit, EmployeeStatusLog
from django.db import models


def generate_detailed_report_docx(division: Division, date_from: datetime.date, date_to: datetime.date | None = None) -> io.BytesIO:
    """Generate a detailed daily lineup report in DOCX format.

    The resulting document adheres to the format described in the
    specification: a heading in Kazakh indicating the division name and
    date, followed by a table where each status forms a column and the
    rows correspond to (1) quantity of employees, (2) list of names,
    (3) aggregated comments and (4) the applicable date range.  A
    summary paragraph of staffing levels (штат) is appended below the
    table.

    :param division: Division for which to generate the report.
    :param date_from: Start date of the report range (inclusive).
    :param date_to: Optional end date (inclusive).  If omitted the
        report covers a single day.
    :return: BytesIO containing the Word document.
    """
    if date_to is None:
        date_to = date_from

    # Determine the date string for the title.  If the range spans
    # multiple days, include both endpoints.
    if date_from == date_to:
        date_str = date_from.strftime("%d.%m.%Y")
    else:
        date_str = f"{date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}"

    # Create the document and add a heading in Kazakh.
    doc = Document()
    title = f"{division.name} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ {date_str} ЖЫЛҒЫ"
    doc.add_heading(title, level=1)

    # Collect employees by status for the specified date range.  For a
    # multi‑day report the same employee can appear multiple times if
    # their status changes; for simplicity we aggregate names and
    # comments across the range.
    statuses = list(EmployeeStatusType.values)
    status_data: dict[str, dict[str, list[str] | str]] = {}
    for status in statuses:
        status_data[status] = {"count": 0, "names": [], "comments": [], "dates": []}

    current_day = date_from
    while current_day <= date_to:
        # Query all employees in the division with their current status on this day.
        employees = Employee.objects.filter(division=division, is_active=True)
        for employee in employees:
            current_status = employee.get_current_status(date=current_day)
            # Ignore statuses that are not tracked in the enumeration
            if current_status not in status_data:
                continue
            status_data[current_status]["count"] += 1
            status_data[current_status]["names"].append(employee.full_name)
            status_data[current_status]["dates"].append(current_day.strftime("%d.%m.%Y"))
            # Capture comments from status logs for the current day if available.
            log = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from__lte=current_day,
            ).filter(
                models.Q(date_to__gte=current_day) | models.Q(date_to__isnull=True)
            ).order_by("-date_from", "-id").first()
            if log and log.comment:
                status_data[current_status]["comments"].append(log.comment)
        current_day += datetime.timedelta(days=1)

    # Prepare the table.  The first column contains row labels.
    table = doc.add_table(rows=5, cols=len(statuses) + 1)
    table.style = 'Table Grid'
    # Header row: leave first cell blank and fill in status labels.
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = ""
    for idx, status in enumerate(statuses, start=1):
        try:
            label = EmployeeStatusType(status).label
        except Exception:
            label = status
        hdr_cells[idx].text = label

    # Row 1 – quantities
    qty_cells = table.rows[1].cells
    qty_cells[0].text = "Количество"
    for idx, status in enumerate(statuses, start=1):
        qty_cells[idx].text = str(status_data[status]["count"])

    # Row 2 – list of names
    names_cells = table.rows[2].cells
    names_cells[0].text = "Список ФИО"
    for idx, status in enumerate(statuses, start=1):
        names = status_data[status]["names"]
        names_cells[idx].text = "\n".join(names) if names else "—"

    # Row 3 – comments
    comment_cells = table.rows[3].cells
    comment_cells[0].text = "Комментарий"
    for idx, status in enumerate(statuses, start=1):
        comments = status_data[status]["comments"]
        comment_cells[idx].text = "; ".join(comments) if comments else "—"

    # Row 4 – dates
    date_cells = table.rows[4].cells
    date_cells[0].text = "Дата"
    for idx, status in enumerate(statuses, start=1):
        dates = status_data[status]["dates"]
        # Collapse duplicates and join
        unique_dates = sorted(set(dates))
        date_cells[idx].text = ", ".join(unique_dates) if unique_dates else "—"

    # Calculate staffing summary: Штат = По списку + Вакантные
    # По списку (occupied) is the number of active employees; вакантные are
    # derived from staffing units.
    occupied = Employee.objects.filter(division=division, is_active=True).count()
    staffing_units = StaffingUnit.objects.filter(division=division)
    total_positions = sum(unit.quantity for unit in staffing_units)
    vacant = max(total_positions - occupied, 0)
    summary = f"Штат: {total_positions} (По списку: {occupied}, Вакантные: {vacant})"
    doc.add_paragraph(summary)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer