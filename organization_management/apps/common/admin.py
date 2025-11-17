"""
Django Admin для управления ролями пользователей и системой RBAC
"""
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import UserRole, Role, Permission, RolePermission


# =====================================================
# Новая система RBAC - Django Admin
# =====================================================

class RolePermissionInline(admin.TabularInline):
    """Inline для управления правами роли"""
    model = RolePermission
    extra = 1
    fields = ('permission', 'scope_type', 'is_active')
    autocomplete_fields = ['permission']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('permission')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Админка для управления ролями через БД"""

    list_display = [
        'code',
        'name',
        'hierarchy_level_display',
        'requires_scope',
        'can_edit_statuses',
        'is_active',
        'users_count',
        'permissions_count',
        'sort_order'
    ]

    list_filter = [
        'is_active',
        'hierarchy_level',
        'requires_scope',
        'can_edit_statuses'
    ]

    search_fields = ['code', 'name', 'description']

    readonly_fields = ['created_at', 'updated_at', 'users_count', 'permissions_count']

    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'name', 'description', 'is_active', 'sort_order')
        }),
        ('Свойства роли', {
            'fields': ('hierarchy_level', 'requires_scope', 'can_edit_statuses')
        }),
        ('Статистика', {
            'fields': ('users_count', 'permissions_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [RolePermissionInline]

    def hierarchy_level_display(self, obj):
        """Красивое отображение уровня иерархии"""
        if obj.hierarchy_level is None:
            return format_html('<span style="color: #6c757d;">-</span>')

        levels = {
            0: ('Вся организация', '#17a2b8'),
            1: ('Департамент', '#28a745'),
            2: ('Управление', '#ffc107'),
            3: ('Отдел', '#fd7e14'),
        }
        name, color = levels.get(obj.hierarchy_level, ('Неизвестно', '#000'))
        return format_html(f'<span style="color: {color}; font-weight: bold;">{name}</span>')

    hierarchy_level_display.short_description = 'Уровень иерархии'

    def users_count(self, obj):
        """Количество пользователей с этой ролью"""
        count = obj.users.count()
        if count > 0:
            return format_html(f'<strong>{count}</strong>')
        return count

    users_count.short_description = 'Пользователей'

    def permissions_count(self, obj):
        """Количество прав у роли"""
        count = obj.role_permissions.filter(is_active=True).count()
        return format_html(f'<strong>{count}</strong>')

    permissions_count.short_description = 'Прав'

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('users', 'role_permissions')

    def save_model(self, request, obj, form, change):
        """При сохранении инвалидируем кеш"""
        super().save_model(request, obj, form, change)
        if change:
            obj.invalidate_cache()


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Админка для управления правами доступа"""

    list_display = [
        'code',
        'name',
        'category_display',
        'is_active',
        'roles_count',
        'created_at'
    ]

    list_filter = [
        'category',
        'is_active',
        'created_at'
    ]

    search_fields = ['code', 'name', 'description']

    readonly_fields = ['created_at', 'updated_at', 'roles_count']

    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'name', 'category', 'description', 'is_active')
        }),
        ('Статистика', {
            'fields': ('roles_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def category_display(self, obj):
        """Красивое отображение категории"""
        colors = {
            'staffing': '#17a2b8',
            'vacancy': '#28a745',
            'employee': '#ffc107',
            'status': '#fd7e14',
            'secondment': '#6f42c1',
            'structure': '#20c997',
            'report': '#dc3545',
            'admin': '#e83e8c',
            'audit': '#6c757d',
        }
        color = colors.get(obj.category, '#000')
        return format_html(
            f'<span style="background-color: {color}; color: white; padding: 3px 8px; '
            f'border-radius: 3px; font-size: 0.85em;">{obj.get_category_display()}</span>'
        )

    category_display.short_description = 'Категория'

    def roles_count(self, obj):
        """Количество ролей с этим правом"""
        count = obj.permission_roles.filter(is_active=True).count()
        if count > 0:
            return format_html(f'<strong>{count}</strong>')
        return count

    roles_count.short_description = 'Ролей'

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('permission_roles')


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Админка для управления связями роль-право"""

    list_display = [
        'role_display',
        'permission_display',
        'permission_category',
        'scope_type',
        'is_active',
        'created_at'
    ]

    list_filter = [
        'is_active',
        'scope_type',
        'role',
        'permission__category',
        'created_at'
    ]

    search_fields = [
        'role__code',
        'role__name',
        'permission__code',
        'permission__name'
    ]

    readonly_fields = ['created_at', 'updated_at']

    autocomplete_fields = ['role', 'permission']

    fieldsets = (
        ('Основная информация', {
            'fields': ('role', 'permission', 'scope_type', 'is_active')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def role_display(self, obj):
        """Отображение роли"""
        return f'{obj.role.code} - {obj.role.name}'

    role_display.short_description = 'Роль'
    role_display.admin_order_field = 'role__code'

    def permission_display(self, obj):
        """Отображение права"""
        return obj.permission.code

    permission_display.short_description = 'Право'
    permission_display.admin_order_field = 'permission__code'

    def permission_category(self, obj):
        """Категория права"""
        return obj.permission.get_category_display()

    permission_category.short_description = 'Категория'
    permission_category.admin_order_field = 'permission__category'

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('role', 'permission')


# =====================================================
# Старая система UserRole - Django Admin
# =====================================================

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
