"""
Custom DRF permission classes for the personnel application.

This module is lifted from the original repository and extended to
incorporate additional business rules required by Role‑5 (HR admin)
users.  Notably, Role‑5 permissions now respect the
``division_type_assignment`` field on ``UserProfile``, ensuring that a
Role‑5 user can only interact with divisions of a specific
``DivisionType``.  If ``division_type_assignment`` is ``None`` then all
division types are permitted.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils import timezone
from .models import UserRole, Employee, EmployeeStatusType, Division, SecondmentRequest


class IsReadOnly(BasePermission):
    """
    Allows access only for read‑only requests (GET, HEAD, OPTIONS).
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class BaseRolePermission(BasePermission):
    """
    Base class for role‑based permissions.
    Provides a helper to fetch the user's profile safely.
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
    Allows full access for Role 4 (admin) or superusers.
    """

    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        return request.user.is_superuser or (profile and profile.role == UserRole.ROLE_4)


class IsRole1(BaseRolePermission):
    """
    Allows read‑only access to the entire organisation.
    """

    def has_permission(self, request, view):
        if request.method not in SAFE_METHODS:
            return False
        profile = self.get_profile(request.user)
        return profile and profile.role == UserRole.ROLE_1


class IsRole2(BaseRolePermission):
    """
    Allows read‑only access to the user's own department.  Filtering
    logic is handled in the view's ``get_queryset`` method.
    """

    def has_permission(self, request, view):
        if request.method not in SAFE_METHODS:
            return False
        profile = self.get_profile(request.user)
        return profile and profile.role == UserRole.ROLE_2 and profile.division_assignment


class IsRole3(BaseRolePermission):
    """
    Allows editing within the user's management level.  A user with
    Role 3 cannot perform actions if they themselves are currently
    seconded out.
    """

    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        if not (profile and profile.role == UserRole.ROLE_3 and profile.division_assignment):
            return False
        # Check if the user is seconded out
        try:
            # Determine if the user is currently seconded out by
            # inspecting their current status log.  It is not enough to
            # check for any open secondment log, since the log may have
            # expired.  Use ``get_current_status`` for accuracy.
            employee = Employee.objects.get(user=request.user)
            today = timezone.now().date()
            if employee.get_current_status(date=today) == EmployeeStatusType.SECONDED_OUT:
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


class IsRole5(BaseRolePermission):
    """
    Allows HR admin operations within the user's assigned division scope.
    The scope includes child divisions if ``include_child_divisions`` is
    set on the user's profile.  In addition, if ``division_type_assignment``
    is set, only divisions of that type may be acted upon.  This
    provides fine‑grained control to allow HR admins to manage specific
    tiers of the organisation (e.g. only offices or only management
    divisions).
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
        # Determine the division associated with the object
        if isinstance(obj, Employee):
            target_division = obj.division
        elif isinstance(obj, Division):
            target_division = obj
        elif isinstance(obj, SecondmentRequest):
            # For approvals/rejections, the relevant division is the target division
            if getattr(view, "action", None) in ["approve", "reject", "return_from_secondment"]:
                target_division = obj.to_division
            else:
                target_division = obj.from_division

        if not target_division:
            return False

        # Ensure the target division is within the assigned division's subtree
        current = target_division
        within_scope = False
        while current:
            if current == assigned_division:
                within_scope = True
                break
            current = current.parent_division
        if not within_scope:
            return False

        # Enforce division type assignment if specified
        division_type_assignment = getattr(profile, "division_type_assignment", None)
        if division_type_assignment and target_division.division_type != division_type_assignment:
            return False

        return True


class IsRole6(BaseRolePermission):
    """
    Allows editing within the user's own office/department.  Similar to
    Role 3, Role 6 users cannot operate if they are currently seconded
    out.
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
                status_logs__date_to__isnull=True,
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
