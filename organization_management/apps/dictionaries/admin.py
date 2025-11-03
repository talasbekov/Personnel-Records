from django.contrib import admin
from organization_management.apps.dictionaries import models

@admin.register(models.Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'created_at']
    search_fields = ['name']
    list_filter = ['level']

@admin.register(models.Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'created_at']
    search_fields = ['name']
    list_filter = ['level']
    ordering = ['level', 'name']

admin.site.register(models.StatusType)
admin.site.register(models.DismissalReason)
admin.site.register(models.TransferReason)
admin.site.register(models.VacancyReason)
admin.site.register(models.EducationType)
admin.site.register(models.DocumentType)
admin.site.register(models.SystemSetting)
