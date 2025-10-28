from django.db import models
from django.utils.translation import gettext_lazy as _

from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position


class Staffing(models.Model):
    """Штатное расписание"""
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name='staffing',
        verbose_name=_('Подразделение')
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name='staffing',
        verbose_name=_('Должность')
    )
    quantity = models.PositiveIntegerField(verbose_name=_('Количество штатных единиц'))
    occupied = models.PositiveIntegerField(default=0, verbose_name=_('Занято'))

    class Meta:
        verbose_name = _('Штатное расписание')
        verbose_name_plural = _('Штатные расписания')
        unique_together = ('division', 'position')

    def __str__(self):
        return f'{self.division} - {self.position}'


class Vacancy(models.Model):
    """Вакансия"""
    class VacancyStatus(models.TextChoices):
        OPEN = 'open', _('Открыта')
        CLOSED = 'closed', _('Закрыта')

    staffing = models.ForeignKey(
        Staffing,
        on_delete=models.CASCADE,
        related_name='vacancies',
        verbose_name=_('Штатное расписание')
    )
    status = models.CharField(
        max_length=10,
        choices=VacancyStatus.choices,
        default=VacancyStatus.OPEN,
        verbose_name=_('Статус')
    )
    requirements = models.TextField(verbose_name=_('Требования'))
    responsibilities = models.TextField(verbose_name=_('Обязанности'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Вакансия')
        verbose_name_plural = _('Вакансии')

    def __str__(self):
        return f'{self.staffing.position} ({self.get_status_display()})'
