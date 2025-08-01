from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.contrib.auth.models import User

# When models are stable, you'll import UserRole and EmployeeStatusType like this:
# from .models import UserRole, Employee, EmployeeStatusType


# !!! IMPORTANT: This MockUserRole is a placeholder. !!!
# !!! Replace its usage below with 'UserRole' (imported from .models) !!!
# !!! once the UserRole enum/choices are defined in personnel/models.py !!!
class MockUserRole:
    ROLE_1 = 1  # Чтение всей организации
    ROLE_2 = 2  # Чтение своего департамента
    ROLE_3 = 3  # Чтение своего департамента + редактирование только своего управления
    ROLE_4 = 4  # Полный доступ


class RoleBasePermission(BasePermission):
    """
    Base class for role-based permissions.
    Assumes user.profile exists and has 'role' and 'division_assignment' attributes.
    """

    def get_user_profile(self, user):
        if not user or not user.is_authenticated:
            return None
        try:
            return user.profile
        except User.profile.RelatedObjectDoesNotExist:
            # print(f"DEBUG: User {user.username} has no profile.") # Optional: for server-side debug logging
            return None
        except AttributeError:
            # print(f"DEBUG: User model may not have 'profile' attribute properly set up.") # Optional
            return None


class CanReadEntireOrganization(RoleBasePermission):
    message = "User requires Role 1 (Read All Organization) for this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True  # Superuser overrides role check

        profile = self.get_user_profile(request.user)
        # TODO: Replace MockUserRole with actual UserRole from models
        return profile and profile.role == MockUserRole.ROLE_1


class CanReadOwnDepartment(RoleBasePermission):
    message = "User requires Role 2 (Read Own Department) and an assigned department."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        profile = self.get_user_profile(request.user)
        # TODO: Replace MockUserRole with actual UserRole from models
        return (
            profile
            and profile.role == MockUserRole.ROLE_2
            and profile.division_assignment is not None
        )

    # TODO: Implement has_object_permission for fine-grained checks if needed,
    # or rely on get_queryset filtering in views.


class CanEditOwnManagement(RoleBasePermission):
    message = "User requires Role 3 (Edit Own Management), an assigned management, and must not be seconded out."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        profile = self.get_user_profile(request.user)
        # TODO: Replace MockUserRole with actual UserRole from models
        if not (
            profile
            and profile.role == MockUserRole.ROLE_3
            and profile.division_assignment is not None
        ):
            return False

        # Placeholder for 'Откомандирован' (seconded out) check.
        # This requires Employee model and EmployeeStatusLog model.
        # from .models import Employee, EmployeeStatusType # Import when models are stable
        # try:
        #   # Assumes Employee model has a OneToOneField to User, e.g., request.user.employee_record
        #   employee_record = request.user.employee_record
        #   is_seconded_out = employee_record.status_logs.filter(
        #       status=EmployeeStatusType.SECONDED_OUT, # Assumes SECONDED_OUT is defined
        #       date_to__isnull=True # Active secondment
        #   ).exists()
        #   if is_seconded_out:
        #       self.message = "User is currently seconded out and cannot edit their original management."
        #       return False
        # except (User.employee_record.RelatedObjectDoesNotExist, AttributeError):
        #   self.message = "Cannot verify secondment status: Employee record not linked to user."
        #   return False # Or True, based on policy if record missing implies they can/cannot edit

        return True  # If all checks pass


class HasFullAccess(RoleBasePermission):
    message = "User requires Role 4 (Full Access) for this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        profile = self.get_user_profile(request.user)
        # TODO: Replace MockUserRole with actual UserRole from models
        return profile and profile.role == MockUserRole.ROLE_4
