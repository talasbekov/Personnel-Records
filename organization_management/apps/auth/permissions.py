from rest_framework import permissions
from organization_management.apps.auth.models import UserRole


class IsRole1(permissions.BasePermission):
    """Доступ только для пользователей с ролью 1."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_1


class IsRole2(permissions.BasePermission):
    """Доступ только для пользователей с ролью 2."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_2


class IsRole3(permissions.BasePermission):
    """Доступ только для пользователей с ролью 3."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_3


class IsRole4(permissions.BasePermission):
    """Доступ только для пользователей с ролью 4 (полный доступ)."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_4


class IsRole5(permissions.BasePermission):
    """Доступ только для пользователей с ролью 5."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_5


class IsRole6(permissions.BasePermission):
    """Доступ только для пользователей с ролью 6."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_6


class IsReadOnly(permissions.BasePermission):
    """Разрешает только безопасные методы (GET, HEAD, OPTIONS)."""
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
