from __future__ import annotations
from django.db import models
from django.utils.translation import gettext_lazy as _
import json

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
