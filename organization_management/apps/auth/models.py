from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Модель пользователя системы"""

    class RoleType(models.TextChoices):
        OBSERVER_ORG = 'role_1', 'Наблюдатель организации'
        OBSERVER_DEPT = 'role_2', 'Наблюдатель департамента'
        DIRECTORATE_HEAD = 'role_3', 'Начальник управления'
        SYSTEM_ADMIN = 'role_4', 'Системный администратор'
        HR_ADMIN = 'role_5', 'Кадровый администратор'
        DIVISION_HEAD = 'role_6', 'Начальник отдела'

    role = models.CharField(
        max_length=10,
        choices=RoleType.choices,
        default=RoleType.OBSERVER_ORG
    )
    division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    is_seconded = models.BooleanField(default=False)

    class Meta:
        db_table = 'users'
