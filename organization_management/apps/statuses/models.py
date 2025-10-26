from __future__ import annotations
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class EmployeeStatusType(models.TextChoices):
    """Статусы сотрудников согласно ТЗ п.6.1"""
    ON_DUTY_SCHEDULED = "ON_DUTY_SCHEDULED", _("В строю")  # Статус по умолчанию
    ON_DUTY_ACTUAL = "ON_DUTY_ACTUAL", _("На дежурстве")
    AFTER_DUTY = "AFTER_DUTY", _("После дежурства")
    BUSINESS_TRIP = "BUSINESS_TRIP", _("В командировке")
    TRAINING_ETC = "TRAINING_ETC", _("Учёба/соревнования/конференция")
    ON_LEAVE = "ON_LEAVE", _("В отпуске")
    SICK_LEAVE = "SICK_LEAVE", _("На больничном")
    SECONDED_OUT = "SECONDED_OUT", _("Откомандирован")
    SECONDED_IN = "SECONDED_IN", _("Прикомандирован")


class EmployeeStatusLog(models.Model):
    """Журнал статусов сотрудников"""
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="status_logs",
        verbose_name=_("Сотрудник")
    )
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatusType.choices,
        default=EmployeeStatusType.ON_DUTY_SCHEDULED,
        verbose_name=_("Статус")
    )
    date_from = models.DateField(
        verbose_name=_("Дата начала"),
        db_index=True
    )
    date_to = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Дата окончания"),
        db_index=True
    )
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Комментарий")
    )
    secondment_division = models.ForeignKey(
        "divisions.Division",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seconded_employees_log_entries",
        verbose_name=_("Подразделение прикомандирования")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_status_logs",
        verbose_name=_("Создано пользователем")
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_status_logs",
        verbose_name=_("Обновлено пользователем")
    )
    is_auto_copied = models.BooleanField(
        default=False,
        verbose_name=_("Автоматически скопировано"),
        help_text=_("True если статус был автоматически скопирован с предыдущего дня")
    )

    class Meta:
        ordering = ["-date_from", "-id"]
        indexes = [
            models.Index(fields=["employee", "date_from", "date_to"]),
            models.Index(fields=["status", "date_from"]),
            models.Index(fields=["is_auto_copied"]),
        ]
        verbose_name = _("Журнал статусов")
        verbose_name_plural = _("Журналы статусов")

    def clean(self):
        """Валидация пересечений статусов"""
        if self.date_to and self.date_from > self.date_to:
            raise ValidationError(_("Дата окончания не может быть раньше даты начала"))

        # Проверка пересечений с другими статусами
        overlapping = EmployeeStatusLog.objects.filter(
            employee=self.employee,
            date_from__lte=self.date_to if self.date_to else timezone.now().date() + timezone.timedelta(days=365)
        ).filter(
            models.Q(date_to__gte=self.date_from) | models.Q(date_to__isnull=True)
        ).exclude(pk=self.pk)

        # Некоторые статусы могут сосуществовать
        coexisting_statuses = [
            EmployeeStatusType.SECONDED_OUT,
            EmployeeStatusType.SECONDED_IN
        ]

        if self.status not in coexisting_statuses:
            overlapping = overlapping.exclude(status__in=coexisting_statuses)

        if overlapping.exists():
            raise ValidationError(_("Статус пересекается с существующим периодом"))

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_status_display()} ({self.date_from} - {self.date_to or 'текущий'})"


class DivisionStatusUpdate(models.Model):
    """Индикаторы обновления статусов по подразделениям"""
    division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.CASCADE,
        related_name="status_updates",
        verbose_name=_("Подразделение")
    )
    update_date = models.DateField(
        verbose_name=_("Дата обновления"),
        db_index=True
    )
    is_updated = models.BooleanField(
        default=False,
        verbose_name=_("Обновлено"),
        help_text=_("Флаг обновления статусов")
    )
    updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Время обновления")
    )
    updated_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Обновлено пользователем")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["division", "update_date"],
                name="unique_division_update_date"
            )
        ]
        ordering = ["-update_date", "division__name"]
        verbose_name = _("Обновление статусов подразделения")
        verbose_name_plural = _("Обновления статусов подразделений")
        indexes = [
            models.Index(fields=["update_date", "is_updated"]),
        ]

    def mark_as_updated(self, user=None):
        """Отметить как обновленное"""
        self.is_updated = True
        self.updated_at = timezone.now()
        self.updated_by = user
        self.save()

    def __str__(self):
        status_label = _("Обновлено") if self.is_updated else _("Не обновлено")
        return f"{self.division.name} на {self.update_date}: {status_label}"
