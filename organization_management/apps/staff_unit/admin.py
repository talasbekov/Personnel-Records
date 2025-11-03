from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from organization_management.apps.staff_unit.models import (
    Vacancy, StaffUnit
)


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['staff_unit', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['staff_unit__position__name', 'requirements']


@admin.register(StaffUnit)
class StaffUnitAdmin(MPTTModelAdmin):
    list_display = ['division', 'position', 'employee', 'index']
    list_filter = ['division']
    search_fields = ['division__name', 'position__name', 'employee__last_name']
