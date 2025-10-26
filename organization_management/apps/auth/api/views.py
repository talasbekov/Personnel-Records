from __future__ import annotations
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from organization_management.apps.auth.models import User, UserRole
from .serializers import UserProfileSerializer
from organization_management.apps.auth.permissions import IsRole4
from organization_management.apps.employees.models import Employee


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Расширенный сериализатор для JWT токенов с информацией о роли"""

    def validate(self, attrs):
        data = super().validate(attrs)

        try:
            user = User.objects.get(username=self.user.username)
            data['role'] = user.role
            data['role_display'] = UserRole(user.role).label
            data['division_id'] = user.division_assignment.id if user.division_assignment else None
            data['division_name'] = user.division_assignment.name if user.division_assignment else None

            try:
                employee = user.employee
                data['employee_id'] = employee.id
                data['employee_name'] = employee.full_name
            except Employee.DoesNotExist:
                data['employee_id'] = None
                data['employee_name'] = None

        except Exception:
            data['role'] = None
            data['role_display'] = None
            data['division_id'] = None
            data['division_name'] = None

        return data


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user profiles."""

    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['user__username', 'role']
    ordering = ['user__username']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated, IsRole4]
        else:
            permission_classes = [IsAuthenticated, IsRole4]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = User.objects.select_related(
            'division_assignment'
        )

        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(division_assignment_id=division_id)

        return queryset
