from django.db import models
from mptt.models import MPTTModel, TreeForeignKey
from django.utils import timezone

class Division(MPTTModel):
    """Модель подразделения (поддерживает иерархию)"""

    class DivisionType(models.TextChoices):
        ORGANIZATION = 'organization', 'Организация'
        DEPARTMENT = 'department', 'Департамент'
        DIRECTORATE = 'directorate', 'Управление'
        DIVISION = 'division', 'Отдел'

    name = models.CharField(max_length=255, default='')
    code = models.CharField(max_length=50, unique=True, default='')
    division_type = models.CharField(max_length=20, choices=DivisionType.choices, default=DivisionType.ORGANIZATION)
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['order', 'name']

    class Meta:
        db_table = 'divisions'
        verbose_name = 'Подразделение'
        verbose_name_plural = 'Подразделения'
        constraints = [
            models.UniqueConstraint(fields=['parent', 'name'], name='uq_division_name_per_parent')
        ]
        permissions = [
            ("can_view_subordinate_departments", "Может видеть на уровне Департамента"),
        ]

    def __str__(self):
        return self.name
