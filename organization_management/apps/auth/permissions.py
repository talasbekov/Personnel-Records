from rest_framework.permissions import BasePermission
from .models import UserRole

class IsRole1(BasePermission):
    """
    Allows access only to users with role 1.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_1


class IsRole2(BasePermission):
    """
    Allows access only to users with role 2.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_2


class IsRole3(BasePermission):
    """
    Allows access only to users with role 3.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_3


class IsRole4(BasePermission):
    """
    Allows access only to users with role 4 (Полный доступ ко всем функциям).
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_4


class IsRole5(BasePermission):
    """
    Allows access only to users with role 5.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_5


class IsRole6(BasePermission):
    """
    Allows access only to users with role 6.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ROLE_6

class IsReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in ('GET', 'HEAD', 'OPTIONS')
