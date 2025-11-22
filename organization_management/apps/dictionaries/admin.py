from django.contrib import admin
from organization_management.apps.dictionaries import models

@admin.register(models.Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'level', 'created_at']
    search_fields = ['name']
    list_filter = ['category']
    ordering = ['level']

@admin.register(models.Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'created_at']
    search_fields = ['name']
    list_filter = ['level']
    ordering = ['level', 'name']

@admin.register(models.Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_created_by_name', 'message_preview', 'created_at']
    list_filter = ['created_at', 'created_by']
    search_fields = ['message', 'created_by__username', 'created_by__employee__last_name']
    readonly_fields = ['created_by', 'created_at']
    ordering = ['-created_at']

    def get_created_by_name(self, obj):
        """Показывает имя пользователя"""
        if hasattr(obj.created_by, 'employee'):
            employee = obj.created_by.employee
            return f"{employee.last_name} {employee.first_name}"
        return obj.created_by.username
    get_created_by_name.short_description = 'Пользователь'

    def message_preview(self, obj):
        """Показывает первые 100 символов сообщения"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Сообщение'

