from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class DivisionType(models.TextChoices):
    COMPANY = "COMPANY", _("Company")
    DEPARTMENT = "DEPARTMENT", _("Департамент")
    MANAGEMENT = "MANAGEMENT", _("Управление")
    OFFICE = "OFFICE", _(
        "Отдел"
    )  # Changed from 'Отдел' to 'OFFICE' for programmatic consistency


class Division(models.Model):
    # division_id is implicitly created as 'id' (AutoField)
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

    def __str__(self):
        return f"{self.name} ({self.get_division_type_display()})"


class Position(models.Model):
    # position_id is implicitly created as 'id'
    name = models.CharField(max_length=255)
    level = models.SmallIntegerField(
        help_text="Чем меньше — тем выше"
    )  # Level 1 is highest

    def __str__(self):
        return f"{self.name} (Level: {self.level})"

    class Meta:
        ordering = ["level", "name"]


class Employee(models.Model):
    # employee_id is implicitly created as 'id'
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
    # hired_date = models.DateField(null=True, blank=True) # Consider adding for staffing calculations

    def __str__(self):
        return self.full_name


class EmployeeStatusType(models.TextChoices):
    ON_DUTY_SCHEDULED = "IN_LINEUP", _("В строю")  # Default
    ON_DUTY_ACTUAL = "ON_DUTY", _("На дежурстве")
    AFTER_DUTY = "AFTER_DUTY", _("После дежурства")
    BUSINESS_TRIP = "BUSINESS_TRIP", _("В командировке")
    TRAINING_ETC = "TRAINING_ETC", _("Учёба / Соревнования / Конференция")
    ON_LEAVE = "ON_LEAVE", _("В отпуске")
    SICK_LEAVE = "SICK_LEAVE", _("На больничном")
    SECONDED_OUT = "SECONDED_OUT", _("Откомандирован")  # Employee is sent out
    SECONDED_IN = "SECONDED_IN", _("Прикомандирован")  # Employee is received


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
    date_to = models.DateField(null=True, blank=True)  # Can be ongoing
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
    acting_for_position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acting_employees',
        help_text="Position this employee is acting for"
    )
    hired_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    fired_date = models.DateField(null=True, blank=True)

    # Добавить метод для получения текущего статуса
    def get_current_status(self, date=None):
        if date is None:
            date = timezone.now().date()

        status_log = self.status_logs.filter(
            date_from__lte=date
        ).filter(
            models.Q(date_to__gte=date) | models.Q(date_to__isnull=True)
        ).order_by('-date_from').first()

        return status_log.status if status_log else EmployeeStatusType.ON_DUTY_SCHEDULED

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_status_display()} ({self.date_from} to {self.date_to or 'current'})"

    class Meta:
        ordering = ["-date_from", "-id"]


# User Profile to store role and division for JWT/Permissions
class UserRole(models.IntegerChoices):
    ROLE_1 = 1, _("Просмотр всей организации (без редактирования)")
    ROLE_2 = 2, _("Просмотр своего департамента (без редактирования)")
    ROLE_3 = 3, _("Редактирование своего управления")
    ROLE_4 = 4, _("Полный доступ (администратор)")
    ROLE_5 = 5, _("Кадровый администратор подразделения")
    ROLE_6 = 6, _("Редактирование своего отдела")


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.IntegerField(choices=UserRole.choices)
    # division_fk is relevant for roles 2 and 3 to scope their access
    # For Role 3 (Управление), this should point to their Управление.
    # For Role 2 (Департамент), this should point to their Департамент.
    # For Role 1 & 4, this can be null.
    division_assignment = models.ForeignKey(
        Division,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Assigned division for role-based access",
    )
    include_child_divisions = models.BooleanField(
        default=True,
        help_text="For Role-5: whether access includes child divisions"
    )
    division_type_assignment = models.CharField(
        max_length=20,
        choices=DivisionType.choices,
        null=True,
        blank=True,
        help_text="Type of division for Role-5 assignment"
    )

    def __str__(self):
        return f"{self.user.username} - Role: {self.get_role_display()}"


# Добавить в hr_system/personnel/models.py

from django.utils import timezone
import json


# Штатное расписание
class StaffingUnit(models.Model):
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='staffing_units')
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['division', 'position']

    def __str__(self):
        return f"{self.division.name} - {self.position.name} ({self.quantity} units)"

    @property
    def occupied_count(self):
        return self.division.employees.filter(position=self.position, is_active=True).count()

    @property
    def vacant_count(self):
        return max(0, self.quantity - self.occupied_count)


# Вакансии
class Vacancy(models.Model):
    staffing_unit = models.ForeignKey(StaffingUnit, on_delete=models.CASCADE, related_name='vacancies')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    priority = models.IntegerField(choices=[(1, 'High'), (2, 'Medium'), (3, 'Low')], default=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_vacancies')
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='closed_vacancies')

    def __str__(self):
        return f"{self.title} - {self.staffing_unit.division.name}"


# Журнал аудита
class AuditLog(models.Model):
    OPERATION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('STATUS_CHANGE', 'Status Change'),
        ('TRANSFER', 'Transfer'),
        ('SECONDMENT', 'Secondment'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('REPORT_GENERATED', 'Report Generated'),
        ('UNAUTHORIZED_ACCESS', 'Unauthorized Access'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    operation = models.CharField(max_length=30, choices=OPERATION_CHOICES)
    model_name = models.CharField(max_length=50, blank=True)
    object_id = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)  # Stores old/new values
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'user']),
            models.Index(fields=['operation', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user} - {self.operation} - {self.timestamp}"


# Сохраненные документы расхода
class PersonnelReport(models.Model):
    division = models.ForeignKey(Division, on_delete=models.CASCADE)
    report_date = models.DateField()
    file_path = models.FileField(upload_to='personnel_reports/%Y/%m/%d/')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    report_type = models.CharField(max_length=20, choices=[
        ('DAILY', 'Daily'),
        ('PERIOD', 'Period'),
    ], default='DAILY')
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-report_date', '-created_at']

    def __str__(self):
        return f"Report for {self.division.name} - {self.report_date}"


# Уведомления
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('SECONDMENT', 'Secondment'),
        ('STATUS_UPDATE', 'Status Update'),
        ('RETURN_REQUEST', 'Return Request'),
        ('VACANCY_CREATED', 'Vacancy Created'),
        ('TRANSFER', 'Transfer'),
        ('ESCALATION', 'Escalation'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_object_id = models.IntegerField(null=True, blank=True)
    related_model = models.CharField(max_length=50, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


# Запросы на прикомандирование
class SecondmentRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='secondment_requests')
    from_division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='outgoing_secondments')
    to_division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='incoming_secondments')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_secondments')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_secondments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.full_name}: {self.from_division.name} → {self.to_division.name}"


# Индикаторы обновления статусов
class DivisionStatusUpdate(models.Model):
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='status_updates')
    update_date = models.DateField()
    is_updated = models.BooleanField(default=False)
    updated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ['division', 'update_date']

    def __str__(self):
        status = "✓" if self.is_updated else "✗"
        return f"{self.division.name} - {self.update_date} - {status}"
