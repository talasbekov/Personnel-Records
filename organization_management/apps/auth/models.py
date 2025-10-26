from __future__ import annotations
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from organization_management.apps.divisions.models import DivisionType

class UserRole(models.IntegerChoices):
    """Роли пользователей согласно ТЗ"""
    ROLE_1 = 1, _("Просмотр расхода всей организации (без редактирования)")
    ROLE_2 = 2, _("Просмотр расхода только своего департамента (без редактирования)")
    ROLE_3 = 3, _("Просмотр департамента + редактирование только своего управления")
    ROLE_4 = 4, _("Полный доступ ко всем функциям")
    ROLE_5 = 5, _("Кадровый администратор подразделения")
    ROLE_6 = 6, _("Просмотр департамента + редактирование только своего отдела")


class User(AbstractUser):
    """Модель пользователя системы"""
    role = models.IntegerField(
        choices=UserRole.choices,
        verbose_name=_("Роль")
    )
    division_assignment = models.ForeignKey(
        "divisions.Division",
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
        return f"{self.username} - Роль: {self.get_role_display()}"
