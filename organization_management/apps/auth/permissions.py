from rest_framework import permissions
from organization_management.apps.auth.models import UserRole

class IsAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

class IsRole1(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.ROLE_1

class IsRole2(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.ROLE_2

class IsRole3(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.ROLE_3

class IsRole4(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.ROLE_4

class IsRole5(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.ROLE_5

class IsRole6(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.ROLE_6

class IsReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
