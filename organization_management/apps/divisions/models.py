from __future__ import annotations
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

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
        "dictionaries.Position",
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
