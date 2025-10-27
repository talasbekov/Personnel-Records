from django.db import models
from django.conf import settings

class EmployeeStatus(models.Model):
    """Модель статуса сотрудника"""

    class StatusType(models.TextChoices):
        IN_SERVICE = 'in_service', 'В строю'
        VACATION = 'vacation', 'Отпуск'
        SICK_LEAVE = 'sick_leave', 'Больничный'
        BUSINESS_TRIP = 'business_trip', 'Командировка'
        TRAINING = 'training', 'Учёба'
        OTHER_ABSENCE = 'other_absence', 'Отсутствие по иным причинам'
        SECONDED_FROM = 'seconded_from', 'Прикомандирован из'
        SECONDED_TO = 'seconded_to', 'Откомандирован в'

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE)
    status_type = models.CharField(max_length=20, choices=StatusType.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    comment = models.TextField(blank=True)

    # Дополнительная информация
    related_division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Для прикомандирования - подразделение источник/назначение'
    )
    location = models.CharField(max_length=255, blank=True, help_text='Место командировки/учебы')

    # Служебная информация
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_statuses'
        verbose_name = 'Статус сотрудника'
        verbose_name_plural = 'Статусы сотрудников'
        ordering = ['-start_date']
