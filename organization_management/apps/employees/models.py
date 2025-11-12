from django.db import models
from django.utils import timezone

class Employee(models.Model):
    """Модель сотрудника"""

    class Gender(models.TextChoices):
        MALE = 'M', 'Мужской'
        FEMALE = 'F', 'Женский'

    class EmploymentStatus(models.TextChoices):
        WORKING = 'working', 'Работает'
        FIRED = 'fired', 'Уволен'

    # Основная информация
    personnel_number = models.CharField(max_length=20, unique=True, default='000000')
    last_name = models.CharField(max_length=100, default='')
    first_name = models.CharField(max_length=100, default='')
    middle_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(default='1970-01-01')
    gender = models.CharField(max_length=1, choices=Gender.choices, default='M')
    iin = models.CharField(max_length=12, null=True, blank=True)
    photo = models.ImageField(upload_to='employees/photos/', null=True, blank=True)

    # Служебная информация
    rank = models.ForeignKey('dictionaries.Rank', on_delete=models.PROTECT, null=True, blank=True)
    user = models.OneToOneField('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='employee')
    hire_date = models.DateField(default='1970-01-01')
    dismissal_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=10,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.WORKING
    )

    # Контактные данные
    work_phone = models.CharField(max_length=20, null=True, blank=True)
    work_email = models.EmailField(null=True, blank=True)
    personal_phone = models.CharField(max_length=20, null=True, blank=True)
    personal_email = models.EmailField(null=True, blank=True)

    # Дополнительная информация
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name}"


class EmployeeTransferHistory(models.Model):
    """История кадровых перемещений сотрудника"""

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='transfers')
    from_division = models.ForeignKey('divisions.Division', on_delete=models.SET_NULL, null=True, related_name='+')
    to_division = models.ForeignKey('divisions.Division', on_delete=models.SET_NULL, null=True, related_name='+')
    from_position = models.ForeignKey('dictionaries.Position', on_delete=models.SET_NULL, null=True, related_name='+')
    to_position = models.ForeignKey('dictionaries.Position', on_delete=models.SET_NULL, null=True, related_name='+')
    transfer_date = models.DateField(default=timezone.now)
    reason = models.CharField(max_length=255, blank=True)
    is_temporary = models.BooleanField(default=False)
    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'employee_transfers'
        ordering = ['-transfer_date', '-id']
