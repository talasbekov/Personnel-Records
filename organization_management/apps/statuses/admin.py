"""
Настройки админ-панели для управления статусами сотрудников
"""
from django.contrib import admin
from django.utils.html import format_html
from organization_management.apps.statuses.models import (
    EmployeeStatus,
    StatusChangeHistory,
    StatusDocument
)


class StatusChangeHistoryInline(admin.TabularInline):
    """Inline для истории изменений статуса"""
    model = StatusChangeHistory
    extra = 0
    readonly_fields = ['change_type', 'old_value', 'new_value', 'comment', 'changed_by', 'changed_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class StatusDocumentInline(admin.TabularInline):
    """Inline для документов статуса"""
    model = StatusDocument
    extra = 0
    readonly_fields = ['uploaded_at', 'uploaded_by']
    fields = ['title', 'file', 'description', 'uploaded_by', 'uploaded_at']


@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(admin.ModelAdmin):
    """Админ-панель для управления статусами сотрудников"""

    list_display = [
        'employee',
        'status_type_display',
        'state_display',
        'start_date',
        'end_date',
        'is_active_display',
        'created_by',
        'created_at'
    ]

    list_filter = [
        'status_type',
        'state',
        'start_date',
        'created_at',
        'auto_applied'
    ]

    search_fields = [
        'employee__personnel_number',
        'employee__last_name',
        'employee__first_name',
        'comment'
    ]

    readonly_fields = [
        'state',
        'actual_end_date',
        'early_termination_reason',
        'is_notified',
        'auto_applied',
        'created_at',
        'updated_at',
        'effective_end_date_display',
        'is_active_display'
    ]

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'employee',
                'status_type',
                'state'
            )
        }),
        ('Даты', {
            'fields': (
                'start_date',
                'end_date',
                'actual_end_date',
                'effective_end_date_display'
            )
        }),
        ('Дополнительная информация', {
            'fields': (
                'comment',
                'early_termination_reason',
                'location',
                'related_division'
            )
        }),
        ('Служебная информация', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at',
                'is_notified',
                'auto_applied',
                'is_active_display'
            ),
            'classes': ('collapse',)
        })
    )

    inlines = [StatusChangeHistoryInline, StatusDocumentInline]

    date_hierarchy = 'start_date'

    def status_type_display(self, obj):
        """Отображение типа статуса с цветовой индикацией"""
        colors = {
            EmployeeStatus.StatusType.IN_SERVICE: 'green',
            EmployeeStatus.StatusType.VACATION: 'blue',
            EmployeeStatus.StatusType.SICK_LEAVE: 'orange',
            EmployeeStatus.StatusType.BUSINESS_TRIP: 'purple',
            EmployeeStatus.StatusType.TRAINING: 'teal',
            EmployeeStatus.StatusType.OTHER_ABSENCE: 'gray',
            EmployeeStatus.StatusType.SECONDED_FROM: 'brown',
            EmployeeStatus.StatusType.SECONDED_TO: 'brown',
        }
        color = colors.get(obj.status_type, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_type_display()
        )
    status_type_display.short_description = 'Тип статуса'

    def state_display(self, obj):
        """Отображение состояния статуса с цветовой индикацией"""
        colors = {
            EmployeeStatus.StatusState.PLANNED: 'blue',
            EmployeeStatus.StatusState.ACTIVE: 'green',
            EmployeeStatus.StatusState.COMPLETED: 'gray',
            EmployeeStatus.StatusState.CANCELLED: 'red',
        }
        color = colors.get(obj.state, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_state_display()
        )
    state_display.short_description = 'Состояние'

    def is_active_display(self, obj):
        """Отображение активности статуса"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Активен</span>')
        elif obj.is_planned:
            return format_html('<span style="color: blue;">○ Запланирован</span>')
        else:
            return format_html('<span style="color: gray;">✗ Неактивен</span>')
    is_active_display.short_description = 'Активность'

    def effective_end_date_display(self, obj):
        """Отображение эффективной даты окончания"""
        return obj.effective_end_date or '-'
    effective_end_date_display.short_description = 'Эффективная дата окончания'

    def save_model(self, request, obj, form, change):
        """Сохранение модели с установкой пользователя"""
        if not change:  # Если создание нового объекта
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('employee', 'related_division', 'created_by')


@admin.register(StatusChangeHistory)
class StatusChangeHistoryAdmin(admin.ModelAdmin):
    """Админ-панель для истории изменений статусов"""

    list_display = [
        'status',
        'change_type',
        'changed_by',
        'changed_at'
    ]

    list_filter = [
        'change_type',
        'changed_at'
    ]

    search_fields = [
        'status__employee__last_name',
        'comment'
    ]

    readonly_fields = [
        'status',
        'change_type',
        'old_value',
        'new_value',
        'comment',
        'changed_by',
        'changed_at'
    ]

    date_hierarchy = 'changed_at'

    def has_add_permission(self, request):
        """Запрет добавления записей вручную"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрет удаления записей"""
        return False


@admin.register(StatusDocument)
class StatusDocumentAdmin(admin.ModelAdmin):
    """Админ-панель для документов статусов"""

    list_display = [
        'title',
        'status',
        'uploaded_by',
        'uploaded_at'
    ]

    list_filter = [
        'uploaded_at'
    ]

    search_fields = [
        'title',
        'description',
        'status__employee__last_name'
    ]

    readonly_fields = [
        'uploaded_at',
        'uploaded_by'
    ]

    date_hierarchy = 'uploaded_at'

    def save_model(self, request, obj, form, change):
        """Сохранение модели с установкой пользователя"""
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('status__employee', 'uploaded_by')
