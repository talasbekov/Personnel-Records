from __future__ import annotations
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class SecondmentStatus(models.TextChoices):
    PENDING = "PENDING", _("Ожидает")
    APPROVED = "APPROVED", _("Одобрено")
    REJECTED = "REJECTED", _("Отклонено")
    CANCELLED = "CANCELLED", _("Отменено")
    RETURNED = "RETURNED", _("Возвращен")


class SecondmentRequest(models.Model):
    """Запросы на прикомандирование/откомандирование"""
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="secondment_requests",
        verbose_name=_("Сотрудник")
    )
    from_division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.CASCADE,
        related_name="outgoing_secondments",
        verbose_name=_("Из подразделения")
    )
    to_division = models.ForeignKey(
        "divisions.Division",
        on_delete=models.CASCADE,
        related_name="incoming_secondments",
        verbose_name=_("В подразделение")
    )
    requested_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        related_name="requested_secondments",
        verbose_name=_("Запросил")
    )
    approved_by = models.ForeignKey(
        get_user_model(),
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
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_returns",
        verbose_name=_("Возврат запросил")
    )
    return_approved_by = models.ForeignKey(
        get_user_model(),
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

    def __str__(self):
        return f"{self.employee.full_name}: {self.from_division.name} → {self.to_division.name}"
