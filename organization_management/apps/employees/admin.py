from django.contrib import admin
from organization_management.apps.employees.models import Employee, EmployeeTransferHistory


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['personnel_number', 'last_name', 'first_name', 'middle_name',
                    'position', 'division', 'employment_status', 'hire_date']
    list_filter = ['employment_status', 'gender', 'division']
    search_fields = ['personnel_number', 'last_name', 'first_name', 'middle_name',
                     'work_email', 'personal_email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('personnel_number', 'last_name', 'first_name', 'middle_name',
                      'birth_date', 'gender', 'photo')
        }),
        ('Служебная информация', {
            'fields': ('division', 'position', 'hire_date', 'dismissal_date', 'employment_status')
        }),
        ('Контактные данные', {
            'fields': ('work_phone', 'work_email', 'personal_phone', 'personal_email')
        }),
        ('Дополнительная информация', {
            'fields': ('rank', 'education', 'specialty', 'notes')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmployeeTransferHistory)
class EmployeeTransferHistoryAdmin(admin.ModelAdmin):
    list_display = ['employee', 'from_division', 'to_division', 'from_position',
                    'to_position', 'transfer_date', 'is_temporary']
    list_filter = ['is_temporary', 'transfer_date']
    search_fields = ['employee__last_name', 'employee__first_name', 'reason']
    readonly_fields = ['created_at']
