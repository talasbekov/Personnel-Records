from django.db import models
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.employees.models import Employee


class Vacancy(models.Model):
    """Вакансия"""
    class VacancyStatus(models.TextChoices):
        OPEN = 'open', _('Открыта')
        CLOSED = 'closed', _('Закрыта')

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
        db_table = 'vacancies'
        verbose_name = _('Вакансия')
        verbose_name_plural = _('Вакансии')
        permissions = [
            ('view_vacancies', 'Просмотр вакансий'),
            ('view_vacancies_division', 'Просмотр вакансий подразделения'),
            ('create_vacancy', 'Создание вакансии'),
            ('create_vacancy_division', 'Создание вакансии в подразделении'),
            ('edit_vacancy', 'Редактирование вакансии'),
            ('close_vacancy', 'Закрытие вакансии'),
            ('fill_vacancy', 'Заполнение вакансии'),
            ('publish_vacancy', 'Публикация вакансии'),
            ('unpublish_vacancy', 'Снятие вакансии с публикации'),
        ]

    def __str__(self):
        return f'{self.id} {self.status} ({self.requirements}) ({self.responsibilities})'


class StaffUnit(MPTTModel):
    """Конкретная штатная единица (слот) для пары division+position."""

    division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        related_name='staff_units',
        verbose_name=_('Подразделение'),
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        related_name='staff_units',
        verbose_name=_('Должность'),
    )
    employee = models.OneToOneField(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='staff_unit',
        verbose_name=_('Сотрудник'),
    )
    vacancy = models.OneToOneField(
        Vacancy,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='staff_unit',
        verbose_name=_('Вакансия'),
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    index = models.PositiveIntegerField(verbose_name=_('Номер слота'))

    class MPTTMeta:
        order_insertion_by = ['index', 'division', 'position']

    class Meta:
        db_table = 'staff_units'
        verbose_name = _('Штатная единица')
        verbose_name_plural = _('Штатные единицы')
        unique_together = ('division', 'position')
        permissions = [
            ('view_staffing_table', 'Просмотр штатного расписания'),
            ('view_staffing_table_division', 'Просмотр штатного расписания подразделения'),
            ('view_staffing_table_all', 'Просмотр штатного расписания всей организации'),
            ('view_position_quota', 'Просмотр квоты должностей'),
            ('view_staffing_statistics', 'Просмотр статистики по штатному расписанию'),
            ('manage_staffing_table', 'Полное управление штатным расписанием'),
            ('manage_staffing_table_division', 'Управление штатным расписанием подразделения'),
            ('create_staffing_position', 'Создание штатной позиции'),
            ('edit_staffing_position', 'Редактирование штатной позиции'),
            ('delete_staffing_position', 'Удаление штатной позиции'),
            ('change_position_quota', 'Изменение квоты должностей'),
            ('reserve_position', 'Резервирование должности'),
        ]

    def __str__(self):
        emp_name = f"{self.employee}" if self.employee else "Вакансия"
        return f"{self.division} - {self.position} - {emp_name} #{self.index}"
