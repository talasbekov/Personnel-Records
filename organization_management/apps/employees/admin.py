from django.contrib import admin
from django.utils.html import format_html
from organization_management.apps.employees.models import Employee, EmployeeTransferHistory


class HasUserFilter(admin.SimpleListFilter):
    """Фильтр для отображения сотрудников с/без привязанного пользователя"""
    title = 'Наличие пользователя'
    parameter_name = 'has_user'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'С пользователем'),
            ('no', 'Без пользователя'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(user__isnull=False)
        if self.value() == 'no':
            return queryset.filter(user__isnull=True)
        return queryset


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['personnel_number', 'last_name', 'first_name', 'middle_name',
                    'rank', 'employment_status', 'user_info_display', 'hire_date']
    list_filter = ['employment_status', 'gender', 'rank', HasUserFilter]
    search_fields = ['personnel_number', 'last_name', 'first_name', 'middle_name',
                     'work_email', 'personal_email', 'user__username', 'user__email', 'iin']
    readonly_fields = ['created_at', 'updated_at', 'user_detail_display']
    autocomplete_fields = ['user']  # Автодополнение для выбора пользователя
    fieldsets = (
        ('Основная информация', {
            'fields': ('personnel_number', 'last_name', 'first_name', 'middle_name',
                      'birth_date', 'gender', 'photo', 'iin')
        }),
        ('Привязка к пользователю', {
            'fields': ('user', 'user_detail_display'),
            'description': 'Связь сотрудника с учетной записью пользователя системы'
        }),
        ('Служебная информация', {
            'fields': ('rank', 'hire_date', 'dismissal_date', 'employment_status')
        }),
        ('Контактные данные', {
            'fields': ('work_phone', 'work_email', 'personal_phone', 'personal_email')
        }),
        ('Дополнительная информация', {
            'fields': ('notes',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_info_display(self, obj):
        """Отображение информации о пользователе в списке"""
        if obj.user:
            # Показываем username с иконкой и цветом
            icon = '✅'
            color = '#28a745'
            info = f'{icon} <b>{obj.user.username}</b>'
            if obj.user.email:
                info += f'<br><small style="color: #666;">{obj.user.email}</small>'
            return format_html(f'<span style="color: {color};">{info}</span>')
        else:
            # Показываем что пользователь не привязан
            return format_html('<span style="color: #dc3545;">❌ Нет пользователя</span>')

    user_info_display.short_description = 'Пользователь'
    user_info_display.admin_order_field = 'user'

    def user_detail_display(self, obj):
        """Детальная информация о пользователе в форме редактирования"""
        if obj.user:
            user = obj.user
            info_parts = [
                f'<div style="padding: 10px; background: #f8f9fa; border-radius: 5px;">',
                f'<p><b>Username:</b> {user.username}</p>',
                f'<p><b>Email:</b> {user.email or "<i>не указан</i>"}</p>',
                f'<p><b>ФИО в системе:</b> {user.get_full_name() or "<i>не указано</i>"}</p>',
                f'<p><b>Статус:</b> ',
            ]

            # Статусы пользователя
            statuses = []
            if user.is_superuser:
                statuses.append('<span style="color: #dc3545;">👑 Суперпользователь</span>')
            if user.is_staff:
                statuses.append('<span style="color: #007bff;">🔧 Персонал</span>')
            if user.is_active:
                statuses.append('<span style="color: #28a745;">✓ Активен</span>')
            else:
                statuses.append('<span style="color: #dc3545;">✗ Неактивен</span>')

            info_parts.append(' | '.join(statuses))
            info_parts.append('</p>')

            # Последний вход
            if user.last_login:
                info_parts.append(f'<p><b>Последний вход:</b> {user.last_login.strftime("%d.%m.%Y %H:%M")}</p>')
            else:
                info_parts.append('<p><b>Последний вход:</b> <i>никогда</i></p>')

            # Роль пользователя
            try:
                if hasattr(user, 'role_info'):
                    role = user.role_info
                    info_parts.append(f'<p><b>Роль:</b> {role.get_role_display()}</p>')
                    if role.effective_scope_division:
                        info_parts.append(f'<p><b>Подразделение:</b> {role.effective_scope_division.name}</p>')
            except Exception:
                pass

            info_parts.append('</div>')

            return format_html(''.join(info_parts))
        else:
            return format_html(
                '<div style="padding: 10px; background: #fff3cd; border-radius: 5px; color: #856404;">'
                '⚠️ Пользователь не привязан к этому сотруднику'
                '</div>'
            )

    user_detail_display.short_description = 'Информация о пользователе'


@admin.register(EmployeeTransferHistory)
class EmployeeTransferHistoryAdmin(admin.ModelAdmin):
    list_display = ['employee', 'from_division', 'to_division', 'from_position',
                    'to_position', 'transfer_date', 'is_temporary']
    list_filter = ['is_temporary', 'transfer_date']
    search_fields = ['employee__last_name', 'employee__first_name', 'reason']
    readonly_fields = ['created_at']
