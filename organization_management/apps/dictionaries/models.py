from __future__ import annotations
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Position(models.Model):
    """Справочник должностей согласно ТЗ"""
    name = models.CharField(max_length=255, verbose_name=_("Название должности"))
    level = models.SmallIntegerField(
        verbose_name=_("Уровень"),
        help_text=_("Чем меньше число, тем выше должность")
    )
    category = models.CharField(max_length=10, null=True, verbose_name=_("Категория"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "name"]
        verbose_name = _("Должность")
        verbose_name_plural = _("Должности")
        indexes = [
            models.Index(fields=["level"]),
        ]

    def __str__(self):
        return f"{self.name} (Уровень: {self.level})"


class StatusType(models.Model):
    """Справочник: Типы статусов"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Название"))
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активен"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Тип статуса")
        verbose_name_plural = _("Типы статусов")
        ordering = ['name']

    def __str__(self):
        return self.name


class DismissalReason(models.Model):
    """Справочник: Причины увольнения"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Название"))
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активен"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Причина увольнения")
        verbose_name_plural = _("Причины увольнения")
        ordering = ['name']

    def __str__(self):
        return self.name


class TransferReason(models.Model):
    """Справочник: Причины перевода"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Название"))
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активен"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Причина перевода")
        verbose_name_plural = _("Причины перевода")
        ordering = ['name']

    def __str__(self):
        return self.name


class VacancyReason(models.Model):
    """Справочник: Причины открытия вакансии"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Название"))
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активен"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Причина открытия вакансии")
        verbose_name_plural = _("Причины открытия вакансии")
        ordering = ['name']

    def __str__(self):
        return self.name


class EducationType(models.Model):
    """Справочник: Типы образования"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Название"))
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активен"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Тип образования")
        verbose_name_plural = _("Типы образования")
        ordering = ['name']

    def __str__(self):
        return self.name


class DocumentType(models.Model):
    """Справочник: Типы документов"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Название"))
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активен"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Тип документа")
        verbose_name_plural = _("Типы документов")
        ordering = ['name']

    def __str__(self):
        return self.name


class SystemSetting(models.Model):
    """Справочник: Настройки системы"""
    key = models.CharField(max_length=100, unique=True, verbose_name=_("Ключ"))
    value = models.CharField(max_length=255, verbose_name=_("Значение"))
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Настройка системы")
        verbose_name_plural = _("Настройки системы")
        ordering = ['key']

    def __str__(self):
        return self.key


class Rank(models.Model):
    """Справочник: Звание согласно ТЗ"""
    name = models.CharField(max_length=50, unique=True, verbose_name=_("Звание"))
    level = models.SmallIntegerField(
        verbose_name=_("Уровень"),
        help_text=_("Чем меньше число, тем выше звание")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "name"]
        verbose_name = _("Звание")
        verbose_name_plural = _("Звания")
        indexes = [
            models.Index(fields=["level"]),
        ]

    def __str__(self):
        return f"{self.name} (Уровень: {self.level})"


class Feedback(models.Model):
    """Модель для обратной связи от пользователей"""
    message = models.TextField(verbose_name=_("Сообщение"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedbacks',
        verbose_name=_("Создал")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Дата создания"))

    class Meta:
        verbose_name = _("Обратная связь")
        verbose_name_plural = _("Обратная связь")
        ordering = ['-created_at']

    def __str__(self):
        return f"Обратная связь от {self.created_by} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"