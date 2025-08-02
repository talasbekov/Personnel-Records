from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import UserRole, Employee, EmployeeStatusType, DivisionType, Division, SecondmentRequest

class IsReadOnly(BasePermission):
    """
    Allows access only for read-only requests (GET, HEAD, OPTIONS).
    """
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

class BaseRolePermission(BasePermission):
    """
    Base class for role-based permissions.
    """
    def get_profile(self, user):
        if not user or not user.is_authenticated:
            return None
        try:
            return user.profile
        except user.profile.RelatedObjectDoesNotExist:
            return None

class IsRole4(BaseRolePermission):
    """
    Allows full access for Role 4 (Admin) or superusers.
    """
    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        return request.user.is_superuser or (profile and profile.role == UserRole.ROLE_4)

class IsRole1(BaseRolePermission):
    """
    Allows read-only access to the entire organization.
    """
    def has_permission(self, request, view):
        if request.method not in SAFE_METHODS:
            return False
        profile = self.get_profile(request.user)
        return profile and profile.role == UserRole.ROLE_1

class IsRole2(BaseRolePermission):
    """
    Allows read-only access to their own department.
    Filtering is handled in the view's get_queryset method.
    """
    def has_permission(self, request, view):
        if request.method not in SAFE_METHODS:
            return False
        profile = self.get_profile(request.user)
        return profile and profile.role == UserRole.ROLE_2 and profile.division_assignment

class IsRole3(BaseRolePermission):
    """
    Allows editing within their own management.
    """
    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        if not (profile and profile.role == UserRole.ROLE_3 and profile.division_assignment):
            return False

        # Check if the user is seconded out
        try:
            is_seconded_out = Employee.objects.filter(
                user=request.user,
                status_logs__status=EmployeeStatusType.SECONDED_OUT,
                status_logs__date_to__isnull=True
            ).exists()
            if is_seconded_out:
                return False
        except Employee.DoesNotExist:
            return False # If no employee record, cannot have this role's permissions

        return True

    def has_object_permission(self, request, view, obj):
        profile = self.get_profile(request.user)
        if not profile or not profile.division_assignment:
            return False

        # User's assigned division must be the object itself or its parent
        assigned_division = profile.division_assignment
        if isinstance(obj, Employee):
            return obj.division == assigned_division
        elif isinstance(obj, Division):
            return obj == assigned_division
        return False

class IsRole5(BaseRolePermission):
    """
    Allows HR admin operations within their assigned division scope.
    """
    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        return profile and profile.role == UserRole.ROLE_5 and profile.division_assignment

    def has_object_permission(self, request, view, obj):
        profile = self.get_profile(request.user)
        if not profile or not profile.division_assignment:
            return False

        assigned_division = profile.division_assignment

        target_division = None
        if isinstance(obj, Employee):
            target_division = obj.division
        elif isinstance(obj, Division):
            target_division = obj
        elif isinstance(obj, SecondmentRequest):
            # For approvals/rejections, the relevant division is the target division
            if view.action in ['approve', 'reject']:
                target_division = obj.to_division
            # For creation, we might check the source division
            else:
                target_division = obj.from_division

        if not target_division:
            return False

        # Check if the target division is the assigned one or a child of it.
        current = target_division
        while current:
            if current == assigned_division:
                return True
            current = current.parent_division
        return False

class IsRole6(BaseRolePermission):
    """
    Allows editing within their own office/department.
    """
    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        if not (profile and profile.role == UserRole.ROLE_6 and profile.division_assignment):
            return False

        # Check if the user is seconded out
        try:
            is_seconded_out = Employee.objects.filter(
                user=request.user,
                status_logs__status=EmployeeStatusType.SECONDED_OUT,
                status_logs__date_to__isnull=True
            ).exists()
            if is_seconded_out:
                return False
        except Employee.DoesNotExist:
            return False

        return True

    def has_object_permission(self, request, view, obj):
        profile = self.get_profile(request.user)
        if not profile or not profile.division_assignment:
            return False

        assigned_division = profile.division_assignment
        if isinstance(obj, Employee):
            return obj.division == assigned_division
        elif isinstance(obj, Division):
            return obj == assigned_division
        return False
