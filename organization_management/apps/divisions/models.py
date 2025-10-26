from django.db import models
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey

class DivisionType(models.TextChoices):
    ORGANIZATION = 'organization', _('Организация')
    DEPARTMENT = 'department', _('Департамент')
    DIRECTORATE = 'directorate', _('Управление')
    DIVISION = 'division', _('Отдел')

class Division(MPTTModel):
    """Модель подразделения (поддерживает иерархию)"""

    class DivisionType(models.TextChoices):
        ORGANIZATION = 'organization', _('Организация')
        DEPARTMENT = 'department', _('Департамент')
        DIRECTORATE = 'directorate', _('Управление')
        DIVISION = 'division', _('Отдел')

    name = models.CharField(max_length=255, verbose_name=_("Название"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Код"))
    division_type = models.CharField(
        max_length=20,
        choices=DivisionType.choices,
        verbose_name=_("Тип подразделения")
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_("Родительское подразделение")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Активно"))
    order = models.IntegerField(default=0, verbose_name=_("Порядок сортировки"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['order', 'name']

    class Meta:
        db_table = 'divisions'
        verbose_name = _('Подразделение')
        verbose_name_plural = _('Подразделения')

    def __str__(self):
        return self.name
