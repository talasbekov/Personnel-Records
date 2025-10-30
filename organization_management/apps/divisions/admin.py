from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from organization_management.apps.divisions.models import Division


@admin.register(Division)
class DivisionAdmin(MPTTModelAdmin):
    list_display = ['name', 'code', 'division_type', 'parent', 'is_active', 'order']
    list_filter = ['division_type', 'is_active']
    search_fields = ['name', 'code']
    list_editable = ['order', 'is_active']
    mptt_level_indent = 20
