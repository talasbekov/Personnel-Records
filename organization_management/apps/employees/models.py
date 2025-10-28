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
    personnel_number = models.CharField(max_length=20, unique=True, default='000000')
    last_name = models.CharField(max_length=100, default='')
    first_name = models.CharField(max_length=100, default='')
    middle_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(default='1970-01-01')
    gender = models.CharField(max_length=1, choices=Gender.choices, default='M')
    photo = models.ImageField(upload_to='employees/photos/', null=True, blank=True)

    # Служебная информация
    division = models.ForeignKey('divisions.Division', on_delete=models.PROTECT, null=True)
    position = models.ForeignKey('dictionaries.Position', on_delete=models.PROTECT, null=True)
    hire_date = models.DateField(default='1970-01-01')
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
