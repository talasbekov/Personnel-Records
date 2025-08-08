"""
Models for the personnel management application.

This file implements all models required by the technical specification,
including the organizational hierarchy, employee management, status tracking,
staffing, secondment, and reporting functionality.
"""

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


class DivisionHierarchy(models.TextChoices):
    """Варианты организационной иерархии согласно ТЗ"""
    VARIANT_1 = "VARIANT_1", _("Компания → Департаменты → Управления → Отделы")
    VARIANT_2 = "VARIANT_2", _("Компания → Управления → Отделы")
    VARIANT_3 = "VARIANT_3", _("Компания → Отделы")


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


class UserRole(models.IntegerChoices):
    """Роли пользователей согласно ТЗ"""
    ROLE_1 = 1, _("Просмотр расхода всей организации (без редактирования)")
    ROLE_2 = 2, _("Просмотр расхода только своего департамента (без редактирования)")
    ROLE_3 = 3, _("Просмотр департамента + редактирование только своего управления")
    ROLE_4 = 4, _("Полный доступ ко всем функциям")
    ROLE_5 = 5, _("Кадровый администратор подразделения")
    ROLE_6 = 6, _("Просмотр департамента + редактирование только своего отдела")


class SecondmentStatus(models.TextChoices):
    PENDING = "PENDING", _("Ожидает")
    APPROVED = "APPROVED", _("Одобрено")
    REJECTED = "REJECTED", _("Отклонено")
    CANCELLED = "CANCELLED", _("Отменено")
    RETURNED = "RETURNED", _("Возвращен")


class ReportType(models.TextChoices):
    DAILY = "DAILY", _("На один день")
    PERIOD = "PERIOD", _("За период")


class VacancyPriority(models.IntegerChoices):
    HIGH = 1, _("Высокий")
    MEDIUM = 2, _("Средний")
    LOW = 3, _("Низкий")


# --- Core Models ---

class Division(models.Model):
    """Модель подразделения организации"""
    name = models.CharField(max_length=255, verbose_name=_("Название"))
    code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Код подразделения"),
        help_text=_("Уникальный код подразделения")
    )
    parent_division = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_divisions",
        verbose_name=_("Родительское подразделение")
    )
    division_type = models.CharField(
        max_length=20,
        choices=DivisionType.choices,
        verbose_name=_("Тип подразделения")
    )
    hierarchy_variant = models.CharField(
        max_length=20,
        choices=DivisionHierarchy.choices,
        default=DivisionHierarchy.VARIANT_1,
        verbose_name=_("Вариант иерархии"),
        help_text=_("Вариант организационной иерархии для данной структуры")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Описание"),
        help_text=_("Дополнительная информация о подразделении")
    )
    contact_info = models.TextField(
        blank=True,
        verbose_name=_("Контактная информация")
    )
    head_position = models.ForeignKey(
        "Position",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="headed_divisions",
        verbose_name=_("Должность руководителя")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Подразделение")
        verbose_name_plural = _("Подразделения")
        ordering = ["division_type", "name"]
        indexes = [
            models.Index(fields=["division_type", "parent_division"]),
            models.Index(fields=["code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "parent_division"],
                name="unique_code_per_parent",
                condition=models.Q(code__isnull=False) & ~models.Q(code="")
            )
        ]

    def clean(self):
        """Расширенная валидация для предотвращения некорректной иерархии"""
        super().clean()

        if self.parent_division:
            # Проверка на циклическую зависимость
            ancestor = self.parent_division
            visited = {self.pk}
            while ancestor:
                if ancestor.pk in visited:
                    raise ValidationError(_("Обнаружена циклическая зависимость в иерархии."))
                visited.add(ancestor.pk)
                if ancestor.pk == self.pk:
                    raise ValidationError(_("Невозможно установить потомка в качестве родителя."))
                ancestor = ancestor.parent_division

            # Детальная валидация иерархии согласно ТЗ
            self._validate_hierarchy_detailed()

    def _validate_hierarchy_detailed(self):
        """Детальная валидация соответствия типа подразделения выбранной иерархии"""
        variant = self.hierarchy_variant
        parent_type = self.parent_division.division_type

        # Правила для каждого варианта иерархии
        hierarchy_rules = {
            DivisionHierarchy.VARIANT_1: {
                DivisionType.DEPARTMENT: [DivisionType.COMPANY],
                DivisionType.MANAGEMENT: [DivisionType.DEPARTMENT, DivisionType.COMPANY],  # Может подчиняться напрямую
                DivisionType.OFFICE: [DivisionType.MANAGEMENT, DivisionType.DEPARTMENT, DivisionType.COMPANY],
            },
            DivisionHierarchy.VARIANT_2: {
                DivisionType.MANAGEMENT: [DivisionType.COMPANY],
                DivisionType.OFFICE: [DivisionType.MANAGEMENT, DivisionType.COMPANY],
            },
            DivisionHierarchy.VARIANT_3: {
                DivisionType.OFFICE: [DivisionType.COMPANY],
            }
        }

        allowed_parents = hierarchy_rules.get(variant, {}).get(self.division_type, [])

        if allowed_parents and parent_type not in allowed_parents:
            raise ValidationError(
                _("В варианте %(variant)s подразделение типа %(child_type)s не может подчиняться %(parent_type)s") % {
                    'variant': self.get_hierarchy_variant_display(),
                    'child_type': self.get_division_type_display(),
                    'parent_type': self.parent_division.get_division_type_display()
                }
            )

    def save(self, *args, **kwargs):
        # Автогенерация кода если не указан
        if not self.code:
            prefix = self.division_type[:3].upper()
            last_code = Division.objects.filter(
                division_type=self.division_type
            ).exclude(pk=self.pk).order_by('-code').first()

            if last_code and last_code.code:
                try:
                    num = int(last_code.code.split('-')[-1]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1

            self.code = f"{prefix}-{num:04d}"

        self.full_clean()
        super().save(*args, **kwargs)

    def get_all_descendants(self):
        """Получить всех потомков подразделения"""
        descendants = []
        children = self.child_divisions.all()
        for child in children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants

    def get_all_ancestors(self):
        """Получить всех предков подразделения"""
        ancestors = []
        parent = self.parent_division
        while parent:
            ancestors.append(parent)
            parent = parent.parent_division
        return ancestors

    def get_full_path(self):
        """Получить полный путь в иерархии"""
        path = [self.name]
        parent = self.parent_division
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent_division
        return " → ".join(path)

    def __str__(self):
        return f"{self.name} ({self.get_division_type_display()})"


class Position(models.Model):
    """Справочник должностей согласно ТЗ"""
    name = models.CharField(max_length=255, verbose_name=_("Название должности"))
    level = models.SmallIntegerField(
        verbose_name=_("Уровень"),
        help_text=_("Чем меньше число, тем выше должность")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Описание должности")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Активна"),
        help_text=_("Неактивные должности не отображаются при выборе")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "name"]
        verbose_name = _("Должность")
        verbose_name_plural = _("Должности")
        indexes = [
            models.Index(fields=["level"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} (Уровень: {self.level})"


class Employee(models.Model):
    """Модель сотрудника"""
    user = models.OneToOneField(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Пользователь"),
        help_text=_("Связь с пользователем Django, если применимо")
    )
    full_name = models.CharField(
        max_length=255,
        verbose_name=_("ФИО"),
        db_index=True
    )
    photo = models.ImageField(
        upload_to="employee_photos/%Y/%m/",
        null=True,
        blank=True,
        verbose_name=_("Фото"),
        help_text=_("Фото 3×4")
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        verbose_name=_("Должность")
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name=_("Подразделение")
    )
    acting_for_position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acting_employees",
        verbose_name=_("Должность за счёт"),
        help_text=_("Должность, за счёт которой действует сотрудник")
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

    class Meta:
        verbose_name = _("Сотрудник")
        verbose_name_plural = _("Сотрудники")
        ordering = ["position__level", "full_name"]
        indexes = [
            models.Index(fields=["is_active", "division"]),
            models.Index(fields=["full_name"]),
            models.Index(fields=["employee_number"]),
        ]

    def save(self, *args, **kwargs):
        # Автогенерация табельного номера
        if not self.employee_number:
            last_emp = Employee.objects.exclude(
                pk=self.pk
            ).order_by('-employee_number').first()

            if last_emp and last_emp.employee_number:
                try:
                    num = int(last_emp.employee_number) + 1
                except ValueError:
                    num = 1
            else:
                num = 1

            self.employee_number = str(num).zfill(6)

        super().save(*args, **kwargs)

    def get_current_status(self, date=None):
        """Получить текущий статус сотрудника на указанную дату"""
        if date is None:
            date = timezone.now().date()

        # Ищем активный статус на указанную дату
        status_log = self.status_logs.filter(
            date_from__lte=date
        ).filter(
            models.Q(date_to__gte=date) | models.Q(date_to__isnull=True)
        ).order_by("-date_from", "-id").first()

        return status_log.status if status_log else EmployeeStatusType.ON_DUTY_SCHEDULED

    def get_status_details(self, date=None):
        """Получить детальную информацию о статусе на дату"""
        if date is None:
            date = timezone.now().date()

        status_log = self.status_logs.filter(
            date_from__lte=date
        ).filter(
            models.Q(date_to__gte=date) | models.Q(date_to__isnull=True)
        ).order_by("-date_from", "-id").first()

        if status_log:
            return {
                'status': status_log.status,
                'date_from': status_log.date_from,
                'date_to': status_log.date_to,
                'comment': status_log.comment,
                'secondment_division': status_log.secondment_division
            }
        else:
            return {
                'status': EmployeeStatusType.ON_DUTY_SCHEDULED,
                'date_from': None,
                'date_to': None,
                'comment': None,
                'secondment_division': None
            }

    def is_seconded_out(self, date=None):
        """Проверить, откомандирован ли сотрудник на указанную дату"""
        status = self.get_current_status(date)
        return status == EmployeeStatusType.SECONDED_OUT

    def is_seconded_in(self, date=None):
        """Проверить, прикомандирован ли сотрудник на указанную дату"""
        status = self.get_current_status(date)
        return status == EmployeeStatusType.SECONDED_IN

    def __str__(self):
        return self.full_name


class EmployeeStatusLog(models.Model):
    """Журнал статусов сотрудников"""
    employee = models.ForeignKey(
        Employee,
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
        Division,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seconded_employees_log_entries",
        verbose_name=_("Подразделение прикомандирования")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_status_logs",
        verbose_name=_("Создано пользователем")
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
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


class UserProfile(models.Model):
    """Профиль пользователя с ролями и правами"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("Пользователь")
    )
    role = models.IntegerField(
        choices=UserRole.choices,
        verbose_name=_("Роль")
    )
    division_assignment = models.ForeignKey(
        Division,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Назначенное подразделение"),
        help_text=_("Подразделение для ролевого доступа")
    )
    include_child_divisions = models.BooleanField(
        default=True,
        verbose_name=_("Включать дочерние подразделения"),
        help_text=_("Для Роли-5: включает ли доступ дочерние подразделения")
    )
    division_type_assignment = models.CharField(
        max_length=20,
        choices=DivisionType.choices,
        null=True,
        blank=True,
        verbose_name=_("Тип подразделения для Роли-5"),
        help_text=_("Ограничение по типу подразделения для Роли-5")
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Телефон")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Профиль пользователя")
        verbose_name_plural = _("Профили пользователей")

    def clean(self):
        """Валидация назначений ролей"""
        if self.role in [UserRole.ROLE_2, UserRole.ROLE_3, UserRole.ROLE_5, UserRole.ROLE_6]:
            if not self.division_assignment:
                raise ValidationError(
                    _("Для ролей 2, 3, 5, 6 требуется указать назначенное подразделение")
                )

        if self.role == UserRole.ROLE_5 and self.division_type_assignment:
            if self.division_assignment.division_type != self.division_type_assignment:
                raise ValidationError(
                    _("Тип назначенного подразделения не соответствует ограничению по типу")
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def has_access_to_division(self, division):
        """Проверить, имеет ли пользователь доступ к подразделению"""
        if self.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return True

        if not self.division_assignment:
            return False

        if self.include_child_divisions:
            # Проверяем, является ли division потомком назначенного подразделения
            current = division
            while current:
                if current == self.division_assignment:
                    return True
                current = current.parent_division
            return False
        else:
            return division == self.division_assignment

    def __str__(self):
        return f"{self.user.username} - Роль: {self.get_role_display()}"


# --- Штатное расписание и вакансии ---

class StaffingUnit(models.Model):
    """Штатное расписание"""
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="staffing_units",
        verbose_name=_("Подразделение")
    )
    position = models.ForeignKey(
        Position,
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
        User,
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
        StaffingUnit,
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
        User,
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
        User,
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


# --- Операции и журналирование ---

class DivisionStatusUpdate(models.Model):
    """Индикаторы обновления статусов по подразделениям"""
    division = models.ForeignKey(
        Division,
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
        User,
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


class PersonnelReport(models.Model):
    """Сохраненные документы расхода личного состава"""
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        verbose_name=_("Подразделение")
    )
    report_date = models.DateField(
        verbose_name=_("Дата отчета"),
        db_index=True
    )
    file = models.FileField(
        upload_to="personnel_reports/%Y/%m/%d/",
        verbose_name=_("Файл отчета")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Создано пользователем")
    )
    report_type = models.CharField(
        max_length=20,
        choices=ReportType.choices,
        default=ReportType.DAILY,
        verbose_name=_("Тип отчета")
    )
    date_from = models.DateField(
        verbose_name=_("Дата начала периода")
    )
    date_to = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Дата окончания периода")
    )
    file_format = models.CharField(
        max_length=10,
        default="docx",
        verbose_name=_("Формат файла"),
        choices=[
            ("docx", "Word"),
            ("xlsx", "Excel"),
            ("pdf", "PDF"),
        ]
    )

    class Meta:
        ordering = ["-report_date", "-created_at"]
        verbose_name = _("Отчет по личному составу")
        verbose_name_plural = _("Отчеты по личному составу")
        indexes = [
            models.Index(fields=["report_date", "division"]),
            models.Index(fields=["report_type", "created_at"]),
        ]

    def __str__(self):
        return f"Отчет для {self.division.name} на {self.report_date}"


class SecondmentRequest(models.Model):
    """Запросы на прикомандирование/откомандирование"""
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="secondment_requests",
        verbose_name=_("Сотрудник")
    )
    from_division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="outgoing_secondments",
        verbose_name=_("Из подразделения")
    )
    to_division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="incoming_secondments",
        verbose_name=_("В подразделение")
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="requested_secondments",
        verbose_name=_("Запросил")
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_secondments",
        verbose_name=_("Одобрил")
    )
    status = models.CharField(
        max_length=20,
        choices=SecondmentStatus.choices,
        default=SecondmentStatus.PENDING,
        verbose_name=_("Статус")
    )
    date_from = models.DateField(
        verbose_name=_("Дата начала")
    )
    date_to = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Дата окончания")
    )
    reason = models.TextField(
        verbose_name=_("Причина прикомандирования")
    )
    return_requested = models.BooleanField(
        default=False,
        verbose_name=_("Запрошен возврат")
    )
    return_requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_returns",
        verbose_name=_("Возврат запросил")
    )
    return_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_returns",
        verbose_name=_("Возврат одобрил")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Запрос на прикомандирование")
        verbose_name_plural = _("Запросы на прикомандирование")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "date_from"]),
            models.Index(fields=["employee", "status"]),
        ]

    def approve(self, user):
        """Одобрить запрос на прикомандирование"""
        self.status = SecondmentStatus.APPROVED
        self.approved_by = user
        self.save()

        # Создаем записи в журнале статусов
        EmployeeStatusLog.objects.create(
            employee=self.employee,
            status=EmployeeStatusType.SECONDED_OUT,
            date_from=self.date_from,
            date_to=self.date_to,
            secondment_division=self.to_division,
            comment=f"Откомандирован в {self.to_division.name}",
            created_by=user
        )

    def reject(self, user):
        """Отклонить запрос"""
        self.status = SecondmentStatus.REJECTED
        self.updated_at = timezone.now()
        self.save()

    def request_return(self, user):
        """Запросить возврат сотрудника"""
        self.return_requested = True
        self.return_requested_by = user
        self.save()

    def approve_return(self, user):
        """Одобрить возврат сотрудника"""
        self.status = SecondmentStatus.RETURNED
        self.return_approved_by = user
        self.save()

        # Завершаем текущий статус откомандирования
        current_status = EmployeeStatusLog.objects.filter(
            employee=self.employee,
            status=EmployeeStatusType.SECONDED_OUT,
            date_to__isnull=True
        ).first()

        if current_status:
            current_status.date_to = timezone.now().date()
            current_status.save()

        # Создаем новый статус "В строю"
        EmployeeStatusLog.objects.create(
            employee=self.employee,
            status=EmployeeStatusType.ON_DUTY_SCHEDULED,
            date_from=timezone.now().date(),
            comment="Возвращен из командировки",
            created_by=user
        )

    def __str__(self):
        return f"{self.employee.full_name}: {self.from_division.name} → {self.to_division.name}"


# --- Дополнительные модели для полного соответствия ТЗ ---

class EmployeeTransferLog(models.Model):
    """Журнал переводов сотрудников между подразделениями"""
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="transfer_logs",
        verbose_name=_("Сотрудник")
    )
    from_division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_from",
        verbose_name=_("Из подразделения")
    )
    to_division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_to",
        verbose_name=_("В подразделение")
    )
    from_position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transfers_from_position",
        verbose_name=_("С должности")
    )
    to_position = models.ForeignKey(
        Position,
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
        User,
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


class EscalationRule(models.Model):
    """Правила эскалации для автоматических уведомлений"""
    name = models.CharField(
        max_length=255,
        verbose_name=_("Название правила")
    )
    time_threshold = models.TimeField(
        verbose_name=_("Временной порог"),
        help_text=_("Время, после которого срабатывает эскалация")
    )
    notification_roles = models.JSONField(
        default=list,
        verbose_name=_("Роли для уведомления"),
        help_text=_("Список ролей, которые получат уведомление")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Активно")
    )
    auto_copy_statuses = models.BooleanField(
        default=False,
        verbose_name=_("Автоматически копировать статусы"),
        help_text=_("Копировать статусы с предыдущего дня при срабатывании")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Правило эскалации")
        verbose_name_plural = _("Правила эскалации")
        ordering = ["time_threshold"]

    def __str__(self):
        return f"{self.name} - {self.time_threshold}"
