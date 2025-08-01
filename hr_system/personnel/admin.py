from django.contrib import admin
from .models import (
    Division,
    Position,
    Employee,
    EmployeeStatusLog,
    UserProfile,
)


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("name", "division_type", "parent_division")
    list_filter = ("division_type",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "level")
    search_fields = ("name",)
    ordering = ("level",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "division")
    list_filter = ("division", "position")
    search_fields = ("full_name", "position__name", "division__name")
    raw_id_fields = ("user", "position", "division")
    ordering = ("full_name",)


@admin.register(EmployeeStatusLog)
class EmployeeStatusLogAdmin(admin.ModelAdmin):
    list_display = ("employee", "status", "date_from", "date_to")
    list_filter = ("status", "date_from")
    search_fields = ("employee__full_name", "comment")
    raw_id_fields = ("employee", "secondment_division")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "division_assignment")
    list_filter = ("role",)
    search_fields = ("user__username",)
    raw_id_fields = ("user", "division_assignment")
