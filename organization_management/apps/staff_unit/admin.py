from django.contrib import admin
from django import forms
from mptt.forms import TreeNodeChoiceField
from organization_management.apps.staff_unit.models import (
    Vacancy, StaffUnit
)
from organization_management.apps.divisions.models import Division


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['staff_unit', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['staff_unit__position__name', 'requirements']


class StaffUnitAdminForm(forms.ModelForm):
    """Форма для штатной единицы с иерархическим селектом подразделений"""

    division = TreeNodeChoiceField(
        queryset=Division.objects.all(),
        required=False,
        label='Подразделение',
        empty_label='Выберите подразделение',
    )

    class Meta:
        model = StaffUnit
        fields = '__all__'


@admin.register(StaffUnit)
class StaffUnitAdmin(admin.ModelAdmin):
    form = StaffUnitAdminForm
    list_display = ['id', 'get_division_hierarchy', 'position', 'get_position_level', 'employee', 'index']
    list_filter = ['division']
    search_fields = ['division__name', 'position__name', 'employee__last_name']
    ordering = ['division__tree_id', 'division__lft', 'position__level', 'index']

    def get_division_hierarchy(self, obj):
        """Отображение иерархии подразделения с отступами"""
        if obj.division:
            # Получаем уровень вложенности подразделения
            level = obj.division.level
            indent = '—' * level  # Используем тире для отступа
            return f"{indent} {obj.division.name}"
        return "-"

    get_division_hierarchy.short_description = 'Подразделение'
    get_division_hierarchy.admin_order_field = 'division__tree_id'

    def get_position_level(self, obj):
        """Отображение уровня должности"""
        if obj.position:
            return obj.position.level
        return "-"

    get_position_level.short_description = 'Уровень'
    get_position_level.admin_order_field = 'position__level'
