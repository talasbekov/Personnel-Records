from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

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

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, null=True)
    status_type = models.CharField(max_length=20, choices=StatusType.choices, default=StatusType.IN_SERVICE)
    start_date = models.DateField(default='1970-01-01')
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

    def clean(self):
        # Базовая проверка корректности интервала дат
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("Дата окончания не может быть раньше даты начала.")

        # Запрет пересечений интервалов по одному сотруднику
        if not self.employee_id:
            return
        qs = EmployeeStatus.objects.filter(employee_id=self.employee_id)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        # Пересечение существует, если (s1 <= e2 or e2 is null) и (s2 <= e1 or e1 is null)
        # Здесь self = [start_date, end_date or +inf]
        overlap_qs = qs.filter(
            start_date__lte=self.end_date if self.end_date else self.start_date,
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.start_date)
        )
        if overlap_qs.exists():
            raise ValidationError("У сотрудника уже существует пересекающийся статус в этот период.")
