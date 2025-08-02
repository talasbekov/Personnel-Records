import json
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# --- Enums and Choices ---

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


class SecondmentStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")
    CANCELLED = "CANCELLED", _("Cancelled")


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
    division_type = models.CharField(
        max_length=20,
        choices=DivisionType.choices,
    )

    class Meta:
        verbose_name = "Division"
        verbose_name_plural = "Divisions"

    def clean(self):
        # Prevent cyclical parent relationships
        ancestor = self.parent_division
        while ancestor:
            if ancestor == self:
                raise ValidationError(_("Cannot set a descendant as parent (would create a cycle)."))
            ancestor = ancestor.parent_division

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_division_type_display()})"


class Position(models.Model):
    name = models.CharField(max_length=255)
    level = models.SmallIntegerField(help_text="Чем меньше — тем выше")

    class Meta:
        ordering = ["level", "name"]
        verbose_name = "Position"
        verbose_name_plural = "Positions"

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

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def get_current_status(self, date=None):
        """
        Calculates the employee's status for a given date based on the status logs.
        Default is ON_DUTY_SCHEDULED if no active log exists.
        """
        if date is None:
            date = timezone.now().date()

        status_log = self.status_logs.filter(
            date_from__lte=date
        ).filter(
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
    is_auto_copied = models.BooleanField(
        default=False,
        help_text="True if this status was automatically copied from the previous day.",
    )

    class Meta:
        ordering = ["-date_from", "-id"]
        indexes = [
            models.Index(fields=["employee", "date_from", "date_to"]),
        ]
        verbose_name = "Employee Status Log"
        verbose_name_plural = "Employee Status Logs"

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

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} - Role: {self.get_role_display()}"


# --- Staffing and Vacancy Models ---


class StaffingUnit(models.Model):
    """Штатное расписание"""
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name="staffing_units")
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1, help_text="Количество по штату")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["division", "position"],
                name="unique_staffing_per_division_position",
            )
        ]
        verbose_name = "Staffing Unit"
        verbose_name_plural = "Staffing Units"

    def __str__(self):
        return f"{self.division.name} - {self.position.name} ({self.quantity} units)"

    @property
    def occupied_count(self):
        """Calculates how many positions are filled."""
        return self.division.employees.filter(position=self.position, is_active=True).count()

    @property
    def vacant_count(self):
        """Calculates how many positions are vacant."""
        return max(0, self.quantity - self.occupied_count)


class Vacancy(models.Model):
    """Вакансии"""
    staffing_unit = models.ForeignKey(StaffingUnit, on_delete=models.CASCADE, related_name="vacancies")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    priority = models.IntegerField(choices=[(1, "High"), (2, "Medium"), (3, "Low")], default=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_vacancies")
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_vacancies"
    )

    class Meta:
        verbose_name = "Vacancy"
        verbose_name_plural = "Vacancies"

    def __str__(self):
        return f"{self.title} - {self.staffing_unit.division.name}"


# --- Operations and Logging Models ---


class DivisionStatusUpdate(models.Model):
    """Индикаторы обновления статусов"""
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name="status_updates")
    update_date = models.DateField()
    is_updated = models.BooleanField(default=False)
    updated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["division", "update_date"], name="unique_division_update_date")
        ]
        ordering = ["-update_date", "division__name"]
        verbose_name = "Division Status Update"
        verbose_name_plural = "Division Status Updates"

    def __str__(self):
        status_label = _("Updated") if self.is_updated else _("Not Updated")
        return f"{self.division.name} on {self.update_date}: {status_label}"


class PersonnelReport(models.Model):
    """Сохраненные документы расхода"""
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
        verbose_name = "Personnel Report"
        verbose_name_plural = "Personnel Reports"

    def __str__(self):
        return f"Report for {self.division.name} on {self.report_date}"


class SecondmentRequest(models.Model):
    """Запросы на прикомандирование"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="secondment_requests")
    from_division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name="outgoing_secondments")
    to_division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name="incoming_secondments")
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="requested_secondments")
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_secondments"
    )
    status = models.CharField(max_length=20, choices=SecondmentStatus.choices, default=SecondmentStatus.PENDING)
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Secondment Request"
        verbose_name_plural = "Secondment Requests"

    def __str__(self):
        return f"{self.employee.full_name}: {self.from_division.name} → {self.to_division.name}"
