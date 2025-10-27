from rest_framework import permissions
from organization_management.apps.auth.models import User

class CanViewAllDivisions(permissions.BasePermission):
    """
    Разрешение для Роли 1 (Наблюдатель организации) и Роли 4 (Системный администратор).
    Дает право на просмотр информации по всей организации.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == User.RoleType.OBSERVER_ORG or
            request.user.role == User.RoleType.SYSTEM_ADMIN
        )

class CanViewOwnDepartment(permissions.BasePermission):
    """
    Разрешение для Роли 2 (Наблюдатель департамента).
    Дает право на просмотр информации только по своему департаменту.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated or not request.user.division:
            return False
        # Логика для проверки, что obj относится к департаменту пользователя
        return obj.division.get_root() == request.user.division.get_root()

class CanEditOwnDirectorate(permissions.BasePermission):
    """
    Разрешение для Роли 3 (Начальник управления).
    Дает право на редактирование информации в своем управлении.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated or not request.user.division:
            return False
        if request.method in permissions.SAFE_METHODS:
            return obj.division.get_root() == request.user.division.get_root()
        # Логика для проверки, что obj относится к управлению пользователя
        return obj.division == request.user.division

class IsSystemAdmin(permissions.BasePermission):
    """
    Разрешение для Роли 4 (Системный администратор).
    Полный доступ ко всем функциям.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.RoleType.SYSTEM_ADMIN

class IsHrAdmin(permissions.BasePermission):
    """
    Разрешение для Роли 5 (Кадровый администратор).
    Дает права на управление кадровой информацией.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.RoleType.HR_ADMIN

class CanEditOwnDivision(permissions.BasePermission):
    """
    Разрешение для Роли 6 (Начальник отдела).
    Дает право на редактирование информации в своем отделе.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated or not request.user.division:
            return False
        if request.method in permissions.SAFE_METHODS:
            return obj.division.get_root() == request.user.division.get_root()
        # Логика для проверки, что obj относится к отделу пользователя
        return obj.division == request.user.division
