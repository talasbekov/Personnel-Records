from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class DivisionType(models.TextChoices):
    COMPANY = 'COMPANY', _('Company')
    DEPARTMENT = 'DEPARTMENT', _('Департамент')
    MANAGEMENT = 'MANAGEMENT', _('Управление')
    OFFICE = 'OFFICE', _('Отдел') # Changed from 'Отдел' to 'OFFICE' for programmatic consistency

class Division(models.Model):
    # division_id is implicitly created as 'id' (AutoField)
    name = models.CharField(max_length=255)
    parent_division = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_divisions')
    division_type = models.CharField(
        max_length=20,
        choices=DivisionType.choices,
    )

    def __str__(self):
        return f"{self.name} ({self.get_division_type_display()})"

class Position(models.Model):
    # position_id is implicitly created as 'id'
    name = models.CharField(max_length=255)
    level = models.SmallIntegerField(help_text="Чем меньше — тем выше") # Level 1 is highest

    def __str__(self):
        return f"{self.name} (Level: {self.level})"

    class Meta:
        ordering = ['level', 'name']

class Employee(models.Model):
    # employee_id is implicitly created as 'id'
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, help_text="Link to Django User, if applicable")
    full_name = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='employee_photos/', null=True, blank=True, help_text="Фото 3×4")
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    division = models.ForeignKey(Division, on_delete=models.PROTECT, related_name='employees')
    # hired_date = models.DateField(null=True, blank=True) # Consider adding for staffing calculations

    def __str__(self):
        return self.full_name

class EmployeeStatusType(models.TextChoices):
    ON_DUTY_SCHEDULED = 'IN_LINEUP', _('В строю') # Default
    ON_DUTY_ACTUAL = 'ON_DUTY', _('На дежурстве')
    AFTER_DUTY = 'AFTER_DUTY', _('После дежурства')
    BUSINESS_TRIP = 'BUSINESS_TRIP', _('В командировке')
    TRAINING_ETC = 'TRAINING_ETC', _('Учёба / Соревнования / Конференция')
    ON_LEAVE = 'ON_LEAVE', _('В отпуске')
    SICK_LEAVE = 'SICK_LEAVE', _('На больничном')
    SECONDED_OUT = 'SECONDED_OUT', _('Откомандирован') # Employee is sent out
    SECONDED_IN = 'SECONDED_IN', _('Прикомандирован') # Employee is received

class EmployeeStatusLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='status_logs')
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatusType.choices,
        default=EmployeeStatusType.ON_DUTY_SCHEDULED
    )
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True) # Can be ongoing
    comment = models.TextField(null=True, blank=True)
    # For secondments, we might need to link to the target/source division
    secondment_division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.SET_NULL, related_name='seconded_employees_log_entries')


    def __str__(self):
        return f"{self.employee.full_name} - {self.get_status_display()} ({self.date_from} to {self.date_to or 'current'})"

    class Meta:
        ordering = ['-date_from', '-id']


# User Profile to store role and division for JWT/Permissions
class UserRole(models.IntegerChoices):
    ROLE_1 = 1, _('Чтение всей организации')
    ROLE_2 = 2, _('Чтение своего департамента')
    ROLE_3 = 3, _('Чтение своего департамента + ред. своего управления')
    ROLE_4 = 4, _('Полный доступ')


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.IntegerField(choices=UserRole.choices)
    # division_fk is relevant for roles 2 and 3 to scope their access
    # For Role 3 (Управление), this should point to their Управление.
    # For Role 2 (Департамент), this should point to their Департамент.
    # For Role 1 & 4, this can be null.
    division_assignment = models.ForeignKey(Division, null=True, blank=True, on_delete=models.SET_NULL, help_text="Assigned division for role-based access")

    def __str__(self):
        return f"{self.user.username} - Role: {self.get_role_display()}"
