from collections import defaultdict
import datetime
import io

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# Document generation imports
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


# --- Enums / Choices ---

class DivisionType(models.TextChoices):
    COMPANY = "COMPANY", _("Company")
    DEPARTMENT = "DEPARTMENT", _("Департамент")
    MANAGEMENT = "MANAGEMENT", _("Управление")
    OFFICE = "OFFICE", _("Отдел")


class EmployeeStatusType(models.TextChoices):
    ON_DUTY_SCHEDULED = "IN_LINEUP", _("В строю")
    ON_DUTY_ACTUAL = "ON_DUTY", _("На дежурстве")
    AFTER_DUTY = "AFTER_DUTY", _("После дежурства")
    BUSINESS_TRIP = "BUSINESS_TRIP", _("В командировке")
    TRAINING_ETC = "TRAINING_ETC", _("Учёба / Соревнования / Конференция")
    ON_LEAVE = "ON_LEAVE", _("В отпуске")
    SICK_LEAVE = "SICK_LEAVE", _("На больничном")
    SECONDED_OUT = "SECONDED_OUT", _("Откомандирован")
    SECONDED_IN = "SECONDED_IN", _("Прикомандирован")


class UserRole(models.IntegerChoices):
    ROLE_1 = 1, _("Просмотр всей организации (без редактирования)")
    ROLE_2 = 2, _("Просмотр своего департамента (без редактирования)")
    ROLE_3 = 3, _("Редактирование своего управления")
    ROLE_4 = 4, _("Полный доступ (администратор)")
    ROLE_5 = 5, _("Кадровый администратор подразделения")
    ROLE_6 = 6, _("Редактирование своего отдела")


# --- Core Models ---


class Division(models.Model):
    name = models.CharField(max_length=255)
    parent_division = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_divisions",
    )
    division_type = models.CharField(max_length=20, choices=DivisionType.choices)

    def __str__(self):
        return f"{self.name} ({self.get_division_type_display()})"


class Position(models.Model):
    name = models.CharField(max_length=255)
    level = models.SmallIntegerField(help_text="Чем меньше — тем выше")

    class Meta:
        ordering = ["level", "name"]

    def __str__(self):
        return f"{self.name} (Level: {self.level})"


class Employee(models.Model):
    user = models.OneToOneField(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Link to Django User, if applicable",
    )
    full_name = models.CharField(max_length=255)
    photo = models.ImageField(
        upload_to="employee_photos/", null=True, blank=True, help_text="Фото 3×4"
    )
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    division = models.ForeignKey(
        Division, on_delete=models.PROTECT, related_name="employees"
    )
    acting_for_position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acting_employees",
        help_text="Position this employee is acting for (должность за счёт)",
    )
    hired_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    fired_date = models.DateField(null=True, blank=True)

    def get_current_status(self, date=None):
        if date is None:
            date = timezone.now().date()

        status_log = self.status_logs.filter(date_from__lte=date).filter(
            models.Q(date_to__gte=date) | models.Q(date_to__isnull=True)
        ).order_by("-date_from", "-id").first()

        return status_log.status if status_log else EmployeeStatusType.ON_DUTY_SCHEDULED

    def __str__(self):
        return self.full_name


class EmployeeStatusLog(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="status_logs"
    )
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatusType.choices,
        default=EmployeeStatusType.ON_DUTY_SCHEDULED,
    )
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    secondment_division = models.ForeignKey(
        Division,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seconded_employees_log_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_status_logs",
    )

    class Meta:
        ordering = ["-date_from", "-id"]

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_status_display()} ({self.date_from} to {self.date_to or 'current'})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.IntegerField(choices=UserRole.choices)
    division_assignment = models.ForeignKey(
        Division,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Assigned division for role-based access",
    )
    include_child_divisions = models.BooleanField(
        default=True,
        help_text="For Role-5: whether access includes child divisions",
    )
    division_type_assignment = models.CharField(
        max_length=20,
        choices=DivisionType.choices,
        null=True,
        blank=True,
        help_text="Type of division for Role-5 assignment",
    )

    def __str__(self):
        return f"{self.user.username} - Role: {self.get_role_display()}"


# --- Staffing and Vacancy ---


class StaffingUnit(models.Model):
    division = models.ForeignKey(
        Division, on_delete=models.CASCADE, related_name="staffing_units"
    )
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1, help_text="Количество по штату")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ["division", "position"]
        verbose_name = "Staffing Unit"
        verbose_name_plural = "Staffing Units"

    def __str__(self):
        return f"{self.division.name} - {self.position.name} ({self.quantity} units)"

    @property
    def occupied_count(self):
        return self.division.employees.filter(position=self.position, is_active=True).count()

    @property
    def vacant_count(self):
        return max(0, self.quantity - self.occupied_count)


class Vacancy(models.Model):
    staffing_unit = models.ForeignKey(
        StaffingUnit, on_delete=models.CASCADE, related_name="vacancies"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    priority = models.IntegerField(
        choices=[(1, "High"), (2, "Medium"), (3, "Low")], default=2
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_vacancies"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_vacancies",
    )

    def __str__(self):
        return f"{self.title} - {self.staffing_unit.division.name}"


# --- Status Update / Division Indicators ---


class DivisionStatusUpdate(models.Model):
    division = models.ForeignKey(
        Division, on_delete=models.CASCADE, related_name="status_updates"
    )
    update_date = models.DateField()
    is_updated = models.BooleanField(default=False)
    updated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ["division", "update_date"]
        ordering = ["-update_date", "division__name"]

    def __str__(self):
        status = "Updated" if self.is_updated else "Not Updated"
        return f"{self.division.name} on {self.update_date}: {status}"


# --- Audit Log ---


class AuditLog(models.Model):
    OPERATION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("STATUS_CHANGE", "Status Change"),
        ("TRANSFER", "Transfer"),
        ("SECONDMENT", "Secondment"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("REPORT_GENERATED", "Report Generated"),
        ("UNAUTHORIZED_ACCESS", "Unauthorized Access"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    operation = models.CharField(max_length=30, choices=OPERATION_CHOICES)
    model_name = models.CharField(max_length=50, blank=True, null=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp", "user"]),
            models.Index(fields=["operation"]),
        ]

    def __str__(self):
        return f"Op: {self.operation} by {self.user} at {self.timestamp}"


# --- Reports ---


class PersonnelReport(models.Model):
    division = models.ForeignKey(Division, on_delete=models.CASCADE)
    report_date = models.DateField()
    file = models.FileField(upload_to="personnel_reports/%Y/%m/%d/")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    report_type = models.CharField(
        max_length=20, choices=[("DAILY", "Daily"), ("PERIOD", "Period")], default="DAILY"
    )
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-report_date", "-created_at"]

    def __str__(self):
        return f"Report for {self.division.name} on {self.report_date}"


# --- Notifications and Secondment ---


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("SECONDMENT", "Secondment"),
        ("STATUS_UPDATE", "Status Update"),
        ("RETURN_REQUEST", "Return Request"),
        ("VACANCY_CREATED", "Vacancy Created"),
        ("TRANSFER", "Transfer"),
        ("ESCALATION", "Escalation"),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_model = models.CharField(max_length=50, blank=True, null=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class SecondmentRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="secondment_requests")
    from_division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name="outgoing_secondments")
    to_division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name="incoming_secondments")
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="requested_secondments")
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_secondments"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.full_name}: {self.from_division.name} → {self.to_division.name}"


# --- Service Functions ---


def _gather_descendant_ids(root_division):
    descendant_ids = [root_division.id]
    queue = [root_division]
    visited = {root_division.id}
    while queue:
        current = queue.pop(0)
        for child in current.child_divisions.all():
            if child.id not in visited:
                descendant_ids.append(child.id)
                visited.add(child.id)
                queue.append(child)
    return descendant_ids


def get_division_statistics(division: Division, on_date: datetime.date):
    """
    Calculates personnel statistics for a given division on a specific date.
    """
    # Collect division and descendants
    all_division_ids = _gather_descendant_ids(division)

    # Total staffing
    total_staffing = StaffingUnit.objects.filter(
        division_id__in=all_division_ids
    ).aggregate(total=models.Sum("quantity"))["total"] or 0

    # Employees on list (home division in scope)
    employees_on_list = Employee.objects.filter(
        division_id__in=all_division_ids,
        is_active=True,
        hired_date__lte=on_date,
    ).exclude(fired_date__lte=on_date)

    on_list_count = employees_on_list.count()

    # Status breakdown
    status_counts = defaultdict(int)
    status_details = defaultdict(list)

    for emp in employees_on_list:
        status = emp.get_current_status(date=on_date)
        status_counts[status] += 1

        log_entry = emp.status_logs.filter(
            date_from__lte=on_date,
            status=status,
        ).filter(
            models.Q(date_to__gte=on_date) | models.Q(date_to__isnull=True)
        ).order_by("-date_from", "-id").first()

        details = {
            "full_name": emp.full_name,
            "comment": log_entry.comment if log_entry else "",
            "date_from": log_entry.date_from if log_entry else None,
            "date_to": log_entry.date_to if log_entry else None,
        }
        status_details[status].append(details)

    in_lineup_count = status_counts[EmployeeStatusType.ON_DUTY_SCHEDULED]

    # Seconded-in employees
    seconded_in_requests = SecondmentRequest.objects.filter(
        to_division_id__in=all_division_ids,
        status="APPROVED",
        date_from__lte=on_date,
    ).filter(
        models.Q(date_to__gte=on_date) | models.Q(date_to__isnull=True)
    )
    seconded_in_count = seconded_in_requests.count()

    seconded_in_status_counts = defaultdict(int)
    for req in seconded_in_requests:
        status = req.employee.get_current_status(date=on_date)
        seconded_in_status_counts[status] += 1

    # Assemble
    stats = {
        "division_name": division.name,
        "on_date": on_date,
        "total_staffing": total_staffing,
        "on_list_count": on_list_count,
        "vacant_count": max(0, total_staffing - on_list_count),
        "in_lineup_count": in_lineup_count,
        "seconded_in_count": seconded_in_count,
        "status_counts": dict(status_counts),
        "seconded_in_status_counts": dict(seconded_in_status_counts),
        "status_details": dict(status_details),
    }

    # Sanity checks
    on_list_check = sum(v for v in status_counts.values())
    assert on_list_count == on_list_check
    non_lineup_sum = sum(v for k, v in status_counts.items() if k != EmployeeStatusType.ON_DUTY_SCHEDULED)
    in_lineup_check = on_list_count - non_lineup_sum
    assert in_lineup_count == in_lineup_check

    return stats


# --- Report Generation Helpers ---


def _add_report_table_to_document(document: Document, division_stats: dict):
    # Title
    title_str = (
        f"{division_stats['division_name']} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ "
        f"{division_stats['on_date'].strftime('%d.%m.%Y')} ЖЫЛҒЫ"
    )
    title_paragraph = document.add_paragraph()
    title_run = title_paragraph.add_run(title_str)
    title_run.font.name = "Times New Roman"
    title_run.font.size = Pt(16)
    title_run.bold = True
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Table
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
    table.style = "Table Grid"
    table.autofit = False

    # Headers
    hdr_cells = table.rows[0].cells
    headers = [
        "№",
        "Название управления",
        "Количество по штату",
        "Количество по списку",
        "Вакантные должности",
        "В строю",
    ] + [s.label for s in status_columns]
    for i, header_text in enumerate(headers):
        cell = hdr_cells[i]
        cell.text = header_text
        run = cell.paragraphs[0].runs[0]
        run.font.size = Pt(12)
        run.bold = True
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Data row
    row_cells = table.add_row().cells
    on_list_display = f"{division_stats['on_list_count']}"
    if division_stats["seconded_in_count"] > 0:
        on_list_display += f" +{division_stats['seconded_in_count']}"
    data_row = [
        "1",
        division_stats["division_name"],
        str(division_stats["total_staffing"]),
        on_list_display,
        str(division_stats["vacant_count"]),
        str(division_stats["in_lineup_count"]),
    ]
    for status in status_columns:
        count = division_stats["status_counts"].get(status, 0)
        if status == EmployeeStatusType.SECONDED_IN:
            count = division_stats["seconded_in_count"]
        cell_content = (
            f"{count}\nПодстрока 1\nПодстрока 2\nПодстрока 3\nПодстрока 4"
        )
        data_row.append(cell_content)

    for i, cell_text in enumerate(data_row):
        cell = row_cells[i]
        cell.text = str(cell_text)
        cell.paragraphs[0].runs[0].font.size = Pt(8)

    # Total row
    total_cells = table.add_row().cells
    total_cells[1].text = "Общее"
    total_cells[1].paragraphs[0].runs[0].bold = True
    for i in range(2, num_cols):
        total_cells[i].text = row_cells[i].text
        total_cells[i].paragraphs[0].runs[0].bold = True


def generate_expense_report_docx(division_stats: dict):
    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(1.0)
    section.bottom_margin = Cm(1.0)

    _add_report_table_to_document(document, division_stats)

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def generate_expense_report_xlsx(division_stats: dict):
    wb = Workbook()
    ws = wb.active
    ws.title = "Expense Report"

    title_str = (
        f"{division_stats['division_name']} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ "
        f"{division_stats['on_date'].strftime('%d.%m.%Y')} ЖЫЛҒЫ"
    )
    ws.merge_cells("A1:N1")
    title_cell = ws["A1"]
    title_cell.value = title_str
    title_cell.font = Font(name="Times New Roman", size=16, bold=True)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

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
    headers = [
        "№",
        "Название управления",
        "Количество по штату",
        "Количество по списку",
        "Вакантные должности",
        "В строю",
    ] + [s.label for s in status_columns]
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    on_list_display = f"{division_stats['on_list_count']}"
    if division_stats["seconded_in_count"] > 0:
        on_list_display += f" +{division_stats['seconded_in_count']}"
    data_row = [
        "1",
        division_stats["division_name"],
        str(division_stats["total_staffing"]),
        on_list_display,
        str(division_stats["vacant_count"]),
        str(division_stats["in_lineup_count"]),
    ]
    for status in status_columns:
        count = division_stats["status_counts"].get(status, 0)
        if status == EmployeeStatusType.SECONDED_IN:
            count = division_stats["seconded_in_count"]
        cell_content = (
            f"{count}\nПодстрока 1\nПодстрока 2\nПодстрока 3\nПодстрока 4"
        )
        data_row.append(cell_content)
    ws.append(data_row)
    for cell in ws[3]:
        cell.alignment = Alignment(wrap_text=True)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _create_pdf_page_content(division_stats, styles):
    title_str = (
        f"{division_stats['division_name']} ЖЕКЕ ҚҰРАМЫНЫҢ САПТЫҚ ТІЗІМІ "
        f"{division_stats['on_date'].strftime('%d.%m.%Y')} ЖЫЛҒЫ"
    )
    title = Paragraph(title_str, styles["h1"])

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
    headers = [
        "№",
        "Название управления",
        "Количество по штату",
        "Количество по списку",
        "Вакантные должности",
        "В строю",
    ] + [s.label for s in status_columns]

    on_list_display = f"{division_stats['on_list_count']}"
    if division_stats["seconded_in_count"] > 0:
        on_list_display += f" +{division_stats['seconded_in_count']}"

    data_row = [
        "1",
        division_stats["division_name"],
        str(division_stats["total_staffing"]),
        on_list_display,
        str(division_stats["vacant_count"]),
        str(division_stats["in_lineup_count"]),
    ]
    row_paragraphs = []
    for status in status_columns:
        count = division_stats["status_counts"].get(status, 0)
        if status == EmployeeStatusType.SECONDED_IN:
            count = division_stats["seconded_in_count"]
        cell_content = (
            f"{count}\nПодстрока 1\nПодстрока 2\nПодстрока 3\nПодстрока 4"
        )
        row_paragraphs.append(Paragraph(cell_content.replace("\n", "<br/>"), styles["BodyText"]))

    table_data = [headers, data_row + row_paragraphs]

    style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]
    )

    table = Table(table_data)
    table.setStyle(style)

    return [title, table]


def generate_expense_report_pdf(division_stats: dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

    try:
        pdfmetrics.registerFont(TTFont("Times-Roman", "times.ttf"))
        main_font = "Times-Roman"
    except Exception:
        main_font = "Helvetica"

    styles = getSampleStyleSheet()
    styles["h1"].fontName = main_font
    styles["BodyText"].fontName = main_font

    elements = _create_pdf_page_content(division_stats, styles)
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_periodic_report_docx(division: Division, date_from: datetime.date, date_to: datetime.date):
    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width

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
    wb = Workbook()
    wb.remove(wb.active)

    current_date = date_from
    while current_date <= date_to:
        stats = get_division_statistics(division, current_date)
        ws = wb.create_sheet(title=current_date.strftime("%Y-%m-%d"))
        ws.append([f"Report for {current_date.strftime('%d.%m.%Y')}"])
        current_date += datetime.timedelta(days=1)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_periodic_report_pdf(division: Division, date_from: datetime.date, date_to: datetime.date):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

    try:
        pdfmetrics.registerFont(TTFont("Times-Roman", "times.ttf"))
        main_font = "Times-Roman"
    except Exception:
        main_font = "Helvetica"

    styles = getSampleStyleSheet()
    styles["h1"].fontName = main_font
    styles["BodyText"].fontName = main_font

    elements = []
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
