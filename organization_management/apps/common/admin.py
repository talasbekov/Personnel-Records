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
            'description': 'Укажите подразделение для ролей 2, 3, 5, 6. Для ролей 1 и 4 оставьте пустым.'
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


class CustomUserAdmin(BaseUserAdmin):
    """Кастомная админка для User с отображением роли"""
    inlines = (UserRoleInline,)
    
    list_display = BaseUserAdmin.list_display + ('get_role',)
    
    def get_role(self, obj):
        """Получить роль пользователя"""
        if hasattr(obj, 'role_info'):
            return obj.role_info.get_role_display()
        return '-'
    
    get_role.short_description = 'Роль'


# Перерегистрируем User с нашей кастомной админкой
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
