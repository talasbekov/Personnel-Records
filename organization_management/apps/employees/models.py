from django.db import models

class Employee(models.Model):
    """Модель сотрудника"""

    class Gender(models.TextChoices):
        MALE = 'M', 'Мужской'
        FEMALE = 'F', 'Женский'

    class EmploymentStatus(models.TextChoices):
        WORKING = 'working', 'Работает'
        FIRED = 'fired', 'Уволен'

    # Основная информация
    personnel_number = models.CharField(max_length=20, unique=True)
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField()
    gender = models.CharField(max_length=1, choices=Gender.choices)
    photo = models.ImageField(upload_to='employees/photos/', null=True, blank=True)

    # Служебная информация
    division = models.ForeignKey('divisions.Division', on_delete=models.PROTECT)
    position = models.ForeignKey('dictionaries.Position', on_delete=models.PROTECT)
    hire_date = models.DateField()
    dismissal_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=10,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.WORKING
    )

    # Контактные данные
    work_phone = models.CharField(max_length=20, blank=True)
    work_email = models.EmailField(blank=True)
    personal_phone = models.CharField(max_length=20, blank=True)
    personal_email = models.EmailField(blank=True)

    # Дополнительная информация
    rank = models.CharField(max_length=100, blank=True)
    education = models.TextField(blank=True)
    specialty = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['last_name', 'first_name']

class EmployeeTransferLog(models.Model):
    """Журнал переводов сотрудников между подразделениями"""
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="transfer_logs"
    )
    from_division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_from"
    )
    to_division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_to"
    )
    from_position = models.ForeignKey(
        "dictionaries.Position",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_from_position"
    )
    to_position = models.ForeignKey(
        "dictionaries.Position",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_to_position"
    )
    transfer_date = models.DateField()
    reason = models.TextField(blank=True)
    order_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transfer_date", "-created_at"]

class VacancyPriority(models.IntegerChoices):
    HIGH = 1, "Высокий"
    MEDIUM = 2, "Средний"
    LOW = 3, "Низкий"


class StaffingUnit(models.Model):
    """Штатное расписание"""
    division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.CASCADE,
        related_name="staffing_units"
    )
    position = models.ForeignKey(
        "dictionaries.Position",
        on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(
        default=1
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["division", "position"],
                name="unique_staffing_per_division_position"
            )
        ]

class Vacancy(models.Model):
    """Вакансии"""
    staffing_unit = models.ForeignKey(
        "employees.StaffingUnit",
        on_delete=models.CASCADE,
        related_name="vacancies"
    )
    title = models.CharField(
        max_length=255
    )
    description = models.TextField(
        blank=True
    )
    requirements = models.TextField(
        blank=True
    )
    priority = models.IntegerField(
        choices=VacancyPriority.choices,
        default=VacancyPriority.MEDIUM
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(
        null=True,
        blank=True
    )
