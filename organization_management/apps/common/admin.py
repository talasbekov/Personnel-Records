"""
Django Admin для управления ролями пользователей
"""
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserRole


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """Админка для управления ролями пользователей"""
    
    list_display = [
        'user',
        'role_display',
        'effective_division_display',
        'scope_division',
        'is_seconded',
        'seconded_to',
        'created_at'
    ]
    
    list_filter = [
        'role',
        'is_seconded',
        'created_at'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'scope_division__name'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'role')
        }),
        ('Область видимости', {
            'fields': ('scope_division',),
            'description': (
                '<strong>Важно:</strong> Подразделение автоматически определяется из привязки '
                'User → Employee → StaffUnit → Division. '
                'Заполняйте scope_division вручную только если у пользователя нет Employee записи, '
                'или для принудительного переопределения области видимости. '
                'Для ролей 1 и 4 всегда оставляйте пустым.'
            )
        }),
        ('Откомандирование', {
            'fields': ('is_seconded', 'seconded_to'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    autocomplete_fields = ['user', 'scope_division', 'seconded_to']
    
    def role_display(self, obj):
        """Красивое отображение роли"""
        colors = {
            'ROLE_1': '#17a2b8',  # info
            'ROLE_2': '#6c757d',  # secondary
            'ROLE_3': '#ffc107',  # warning
            'ROLE_4': '#dc3545',  # danger
            'ROLE_5': '#28a745',  # success
            'ROLE_6': '#fd7e14',  # orange
        }
        color = colors.get(obj.role, '#000')
        return f'<span style="color: {color}; font-weight: bold;">{obj.get_role_display()}</span>'

    role_display.short_description = 'Роль'
    role_display.allow_tags = True

    def effective_division_display(self, obj):
        """Отображение эффективного подразделения (автоматически определенного)"""
        division = obj.effective_scope_division
        if division:
            source = ''
            if obj.is_seconded and obj.seconded_to:
                source = ' <span style="color: #dc3545;">(откомандирован)</span>'
            elif hasattr(obj.user, 'employee'):
                try:
                    if hasattr(obj.user.employee, 'staff_unit') and obj.user.employee.staff_unit:
                        source = ' <span style="color: #28a745;">(авто)</span>'
                except:
                    pass
            if not source and obj.scope_division:
                source = ' <span style="color: #6c757d;">(вручную)</span>'
            return f'{division.name}{source}'
        return '<span style="color: #dc3545;">Не определено</span>'

    effective_division_display.short_description = 'Эффективное подразделение'
    effective_division_display.allow_tags = True
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'scope_division', 'seconded_to')


# Расширяем стандартную админку User для отображения роли
class UserRoleInline(admin.StackedInline):
    """Inline для отображения роли в админке User"""
    model = UserRole
    can_delete = False
    verbose_name = 'Роль пользователя'
    verbose_name_plural = 'Роль пользователя'
    fk_name = 'user'
    fields = ('role', 'scope_division', 'is_seconded', 'seconded_to')
    autocomplete_fields = ['scope_division', 'seconded_to']


class EmployeeInline(admin.StackedInline):
    """Inline для отображения сотрудника в админке User"""
    from organization_management.apps.employees.models import Employee
    model = Employee
    can_delete = False
    verbose_name = 'Сотрудник'
    verbose_name_plural = 'Информация о сотруднике'
    fk_name = 'user'
    fields = ('personnel_number', 'last_name', 'first_name', 'middle_name', 'iin', 'rank', 'employment_status')
    readonly_fields = ('personnel_number', 'last_name', 'first_name', 'middle_name', 'iin', 'rank', 'employment_status')
    extra = 0
    max_num = 1

    def has_add_permission(self, request, obj=None):
        """Запрещаем добавление через inline (должно быть создано отдельно)"""
        return False


class CustomUserAdmin(BaseUserAdmin):
    """Кастомная админка для User с отображением роли и сотрудника"""
    inlines = (UserRoleInline, EmployeeInline)

    list_display = BaseUserAdmin.list_display + ('get_role', 'get_employee')

    def get_role(self, obj):
        """Получить роль пользователя"""
        if hasattr(obj, 'role_info'):
            return obj.role_info.get_role_display()
        return '-'

    get_role.short_description = 'Роль'

    def get_employee(self, obj):
        """Получить информацию о сотруднике"""
        if hasattr(obj, 'employee'):
            emp = obj.employee
            return f'{emp.last_name} {emp.first_name} ({emp.personnel_number})'
        return '-'

    get_employee.short_description = 'Сотрудник'


# Перерегистрируем User с нашей кастомной админкой
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
