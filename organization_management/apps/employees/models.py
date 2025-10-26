from __future__ import annotations
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from organization_management.apps.employees.domain.value_objects import FullName, Photo

class Employee(models.Model):
    """Модель сотрудника"""
    user = models.OneToOneField(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Пользователь"),
        help_text=_("Связь с пользователем Django, если применимо")
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)

    photo = models.ImageField(
        upload_to="employee_photos/%Y/%m/",
        null=True,
        blank=True,
        verbose_name=_("Фото"),
        help_text=_("Фото 3×4")
    )
    position = models.ForeignKey(
        "dictionaries.Position",
        on_delete=models.PROTECT,
        verbose_name=_("Должность")
    )
    division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name=_("Подразделение")
    )
    employee_number = models.CharField(
        max_length=50,
        blank=True,
        unique=True,
        verbose_name=_("Табельный номер")
    )
    hired_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Дата приёма на работу")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Активен"),
        help_text=_("Неактивные сотрудники считаются уволенными")
    )
    fired_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Дата увольнения")
    )
    contact_phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Контактный телефон")
    )
    contact_email = models.EmailField(
        blank=True,
        verbose_name=_("Контактный email")
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Примечания")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def full_name(self) -> FullName:
        return FullName(first_name=self.first_name, last_name=self.last_name, middle_name=self.middle_name)

    @full_name.setter
    def full_name(self, value: FullName):
        self.first_name = value.first_name
        self.last_name = value.last_name
        self.middle_name = value.middle_name

    @property
    def photo_vo(self) -> Photo:
        return Photo(image=self.photo)

    class Meta:
        verbose_name = _("Сотрудник")
        verbose_name_plural = _("Сотрудники")
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["is_active", "division"]),
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["employee_number"]),
        ]

    def __str__(self):
        return str(self.full_name)

class EmployeeTransferLog(models.Model):
    """Журнал переводов сотрудников между подразделениями"""
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="transfer_logs",
        verbose_name=_("Сотрудник")
    )
    from_division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_from",
        verbose_name=_("Из подразделения")
    )
    to_division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_to",
        verbose_name=_("В подразделение")
    )
    from_position = models.ForeignKey(
        "dictionaries.Position",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_from_position",
        verbose_name=_("С должности")
    )
    to_position = models.ForeignKey(
        "dictionaries.Position",
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_to_position",
        verbose_name=_("На должность")
    )
    transfer_date = models.DateField(
        verbose_name=_("Дата перевода")
    )
    reason = models.TextField(
        blank=True,
        verbose_name=_("Основание перевода")
    )
    order_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Номер приказа")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Создано пользователем")
    )

    class Meta:
        verbose_name = _("Журнал переводов")
        verbose_name_plural = _("Журнал переводов")
        ordering = ["-transfer_date", "-created_at"]

    def __str__(self):
        return f"{self.employee.full_name}: {self.from_division} → {self.to_division} ({self.transfer_date})"

class VacancyPriority(models.IntegerChoices):
    HIGH = 1, _("Высокий")
    MEDIUM = 2, _("Средний")
    LOW = 3, _("Низкий")


class StaffingUnit(models.Model):
    """Штатное расписание"""
    division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.CASCADE,
        related_name="staffing_units",
        verbose_name=_("Подразделение")
    )
    position = models.ForeignKey(
        "dictionaries.Position",
        on_delete=models.PROTECT,
        verbose_name=_("Должность")
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Количество по штату"),
        help_text=_("Количество штатных единиц")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_staffing_units",
        verbose_name=_("Создано пользователем")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["division", "position"],
                name="unique_staffing_per_division_position"
            )
        ]
        verbose_name = _("Штатная единица")
        verbose_name_plural = _("Штатные единицы")

    @property
    def occupied_count(self):
        """Количество занятых должностей"""
        return self.division.employees.filter(
            position=self.position,
            is_active=True
        ).count()

    @property
    def vacant_count(self):
        """Количество вакантных должностей"""
        return max(0, self.quantity - self.occupied_count)

    @property
    def has_vacancies(self):
        """Есть ли вакансии"""
        return self.vacant_count > 0

    def __str__(self):
        return f"{self.division.name} - {self.position.name} ({self.quantity} единиц)"


class Vacancy(models.Model):
    """Вакансии"""
    staffing_unit = models.ForeignKey(
        "employees.StaffingUnit",
        on_delete=models.CASCADE,
        related_name="vacancies",
        verbose_name=_("Штатная единица")
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_("Название вакансии")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Описание")
    )
    requirements = models.TextField(
        blank=True,
        verbose_name=_("Требования")
    )
    priority = models.IntegerField(
        choices=VacancyPriority.choices,
        default=VacancyPriority.MEDIUM,
        verbose_name=_("Приоритет")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Активна"),
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_vacancies",
        verbose_name=_("Создано пользователем")
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Дата закрытия")
    )
    closed_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_vacancies",
        verbose_name=_("Закрыто пользователем")
    )

    class Meta:
        verbose_name = _("Вакансия")
        verbose_name_plural = _("Вакансии")
        ordering = ["priority", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "priority"]),
        ]

    def close(self, user=None):
        """Закрыть вакансию"""
        self.is_active = False
        self.closed_at = timezone.now()
        self.closed_by = user
        self.save()

    def __str__(self):
        return f"{self.title} - {self.staffing_unit.division.name}"
