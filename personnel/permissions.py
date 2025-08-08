"""
Custom DRF permission classes for the personnel application.

This file replicates the original permission classes while adding
improvements required by the technical specification.  Notably, Role 6
now enforces time‑based restrictions on write operations: users can
edit data only during working hours (08:00–18:00 local time).  The
existing logic preventing actions by seconded‑out users is preserved.
"""

import datetime
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils import timezone

from .models import UserRole, Employee, EmployeeStatusType, Division, SecondmentRequest, DivisionType


class IsReadOnly(BasePermission):
    """Allows access only for read‑only requests (GET, HEAD, OPTIONS)."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class BaseRolePermission(BasePermission):
    """Base class for role‑based permissions providing profile access and
    common checks.

    Subclasses should implement role‑specific logic in ``has_permission``
    and ``has_object_permission``.  This base class provides helper
    methods for retrieving the user's profile and enforcing global
    constraints from the technical specification, such as working
    hour restrictions.
    """

    #: Start of the working day (inclusive)
    WORKING_HOURS_START = datetime.time(8, 0)
    #: End of the working day (inclusive)
    WORKING_HOURS_END = datetime.time(18, 0)

    def get_profile(self, user):
        """Return the associated UserProfile for ``user``, or ``None`` if unavailable."""
        if not user or not user.is_authenticated:
            return None
        try:
            return user.profile
        except user.profile.RelatedObjectDoesNotExist:  # pragma: no cover
            return None

    def within_work_hours(self, request):
        """Return True if write operations occur within configured working hours.

        According to the technical specification, critical operations
        (i.e. those modifying data) must be performed only within a
        defined time window.  Read‑only requests are always allowed.
        """
        if request.method in SAFE_METHODS:
            return True
        now = timezone.localtime().time()
        return (self.WORKING_HOURS_START <= now <= self.WORKING_HOURS_END)


class IsRole4(BaseRolePermission):
    """Allows full access for Role 4 (administrator) or superusers."""

    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        return request.user.is_superuser or (profile and profile.role == UserRole.ROLE_4)


class IsRole1(BaseRolePermission):
    """Read‑only access to the entire organisation."""

    def has_permission(self, request, view):
        if request.method not in SAFE_METHODS:
            return False
        profile = self.get_profile(request.user)
        return profile and profile.role == UserRole.ROLE_1


class IsRole2(BaseRolePermission):
    """Read‑only access to the user's own department."""

    def has_permission(self, request, view):
        if request.method not in SAFE_METHODS:
            return False
        profile = self.get_profile(request.user)
        return profile and profile.role == UserRole.ROLE_2 and profile.division_assignment


class IsRole3(BaseRolePermission):
    """Edit access within the user's management division unless seconded out."""

    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        # Must be role‑3 with an assigned division
        if not (profile and profile.role == UserRole.ROLE_3 and profile.division_assignment):
            return False
        # Enforce working hours for write operations
        if not self.within_work_hours(request):
            return False
        # Deny if the user is currently seconded out
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


class IsRole5(BaseRolePermission):
    """
    HR admin role.  Allows operations within the user's assigned division scope.
    The scope includes child divisions if ``include_child_divisions`` is set.  A
    ``division_type_assignment`` can further restrict access to divisions of a
    specific type.
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
            if getattr(view, "action", None) in ["approve", "reject", "return_from_secondment"]:
                target_division = obj.to_division
            else:
                target_division = obj.from_division
        if not target_division:
            return False
        # Determine whether child divisions are included in the scope
        include_children = getattr(profile, "include_child_divisions", False)
        within_scope = False
        if include_children:
            # Target must be in the subtree rooted at assigned_division
            current = target_division
            while current:
                if current == assigned_division:
                    within_scope = True
                    break
                current = current.parent_division
        else:
            within_scope = (target_division == assigned_division)
        if not within_scope:
            return False
        # Enforce division type assignment if specified
        division_type_assignment = getattr(profile, "division_type_assignment", None)
        if division_type_assignment and target_division.division_type != division_type_assignment:
            return False
        return True


class IsRole6(BaseRolePermission):
    """
    Роль-6: Просмотр департамента + редактирование только своего отдела.
    Согласно ТЗ п.5.1
    """

    def has_permission(self, request, view):
        profile = self.get_profile(request.user)
        if not (profile and profile.role == UserRole.ROLE_6 and profile.division_assignment):
            return False

        # Только чтение для просмотра департамента
        if request.method in SAFE_METHODS:
            return True

        # Проверка рабочего времени для записи
        if not self.within_work_hours(request):
            return False

        # Проверка откомандирования
        try:
            employee = Employee.objects.get(user=request.user)
            if employee.is_seconded_out():
                return False
        except Employee.DoesNotExist:
            pass

        return True

    def has_object_permission(self, request, view, obj):
        profile = self.get_profile(request.user)
        if not profile or not profile.division_assignment:
            return False

        # Для чтения - доступ к департаменту и его подразделениям
        if request.method in SAFE_METHODS:
            if isinstance(obj, (Employee, Division)):
                target_div = obj.division if isinstance(obj, Employee) else obj
                # Находим родительский департамент
                current = target_div
                while current:
                    if current.division_type == DivisionType.DEPARTMENT:
                        # Проверяем, относится ли отдел пользователя к этому департаменту
                        user_dept = profile.division_assignment
                        while user_dept:
                            if user_dept.parent_division == current or user_dept == current:
                                return True
                            user_dept = user_dept.parent_division
                    current = current.parent_division
            return False

        # Для записи - только свой отдел
        if isinstance(obj, Employee):
            return obj.division == profile.division_assignment
        elif isinstance(obj, Division):
            return obj == profile.division_assignment

        return False