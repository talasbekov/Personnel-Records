from rest_framework import viewsets, permissions
from .models import Division, Position, Employee, UserProfile, EmployeeStatusLog
from .serializers import (
    DivisionSerializer,
    PositionSerializer,
    EmployeeSerializer,
    UserProfileSerializer,
    MyTokenObtainPairSerializer,  # Added by subtask
    # EmployeeStatusLogSerializer
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView as OriginalTokenObtainPairView,
)  # Added by subtask


from .permissions import IsRole4, IsRole1, IsRole2, IsRole3, IsRole5, IsRole6, IsReadOnly

from .models import UserRole
from django.db.models import Q

# TODO: Implement proper permissions later based on roles
class DivisionViewSet(viewsets.ModelViewSet):
    serializer_class = DivisionSerializer
    permission_classes = [IsRole4 | (IsReadOnly & (IsRole1 | IsRole2 | IsRole3 | IsRole5 | IsRole6))]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Division.objects.none()

        profile = getattr(user, 'profile', None)
        if not profile:
            return Division.objects.none()

        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return Division.objects.all().prefetch_related("child_divisions")

        assigned_division = profile.division_assignment
        if not assigned_division:
            return Division.objects.none()

        if profile.role in [UserRole.ROLE_2, UserRole.ROLE_5]: # Department or HR Admin
            # Return the assigned division and all its children
            descendant_ids = [assigned_division.id]
            # This is a simple implementation. For large hierarchies, a more efficient method like MPTT would be better.
            children = list(assigned_division.child_divisions.all())
            while children:
                child = children.pop()
                descendant_ids.append(child.id)
                children.extend(list(child.child_divisions.all()))
            return Division.objects.filter(id__in=descendant_ids).prefetch_related("child_divisions")

        if profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]: # Management or Office
            return Division.objects.filter(id=assigned_division.id).prefetch_related("child_divisions")

        return Division.objects.none()


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsRole4 | (IsReadOnly & permissions.IsAuthenticated)]


class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    permission_classes = [IsRole4 | IsRole5 | (IsReadOnly & (IsRole1 | IsRole2 | IsRole3 | IsRole6))]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Employee.objects.none()

        profile = getattr(user, 'profile', None)
        if not profile:
            return Employee.objects.none()

        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return Employee.objects.all().select_related("position", "division")

        assigned_division = profile.division_assignment
        if not assigned_division:
            return Employee.objects.none()

        # Get all descendant division IDs for roles 2 and 5
        descendant_ids = [assigned_division.id]
        if profile.role in [UserRole.ROLE_2, UserRole.ROLE_5]:
            children = list(assigned_division.child_divisions.all())
            while children:
                child = children.pop()
                descendant_ids.append(child.id)
                children.extend(list(child.child_divisions.all()))

        return Employee.objects.filter(division__id__in=descendant_ids).select_related("position", "division")


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all().select_related("user", "division_assignment")
    serializer_class = UserProfileSerializer
    permission_classes = [IsRole4]


# class EmployeeStatusLogViewSet(viewsets.ModelViewSet):
# queryset = EmployeeStatusLog.objects.all()
# serializer_class = EmployeeStatusLogSerializer
# permission_classes = [permissions.IsAuthenticated] # Placeholder


# Custom Token View to use the custom serializer (appended by subtask)
class MyTokenObtainPairView(OriginalTokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
