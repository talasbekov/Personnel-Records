from django.contrib import admin
from organization_management.apps.staffing.models import (
    Staffing, Vacancy, StaffUnit, EmployeeAssignment
)


@admin.register(Staffing)
class StaffingAdmin(admin.ModelAdmin):
    list_display = ['division', 'position', 'quantity', 'occupied']
    list_filter = ['division']
    search_fields = ['division__name', 'position__name']
    readonly_fields = ['occupied']


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['staffing', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['staffing__position__name', 'requirements']


@admin.register(StaffUnit)
class StaffUnitAdmin(admin.ModelAdmin):
    list_display = ['division', 'position', 'index']
    list_filter = ['division']
    search_fields = ['division__name', 'position__name']


@admin.register(EmployeeAssignment)
class EmployeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ['employee', 'staff_unit', 'assignment_type', 'created_at']
    list_filter = ['assignment_type', 'created_at']
    search_fields = ['employee__last_name', 'employee__first_name', 'staff_unit__position__name']
    readonly_fields = ['created_at']
