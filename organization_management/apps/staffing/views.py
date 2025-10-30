from rest_framework import viewsets, permissions

from organization_management.apps.staffing.models import Staffing, Vacancy, StaffUnit, EmployeeAssignment
from organization_management.apps.staffing.serializers import (
    StaffingSerializer,
    VacancySerializer,
    StaffUnitSerializer,
    EmployeeAssignmentSerializer,
)
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.dictionaries.api.serializers import PositionSerializer


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()


class StaffingViewSet(viewsets.ModelViewSet):
    queryset = Staffing.objects.all()
    serializer_class = StaffingSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()


class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()


class StaffUnitViewSet(viewsets.ModelViewSet):
    queryset = StaffUnit.objects.all()
    serializer_class = StaffUnitSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()


class EmployeeAssignmentViewSet(viewsets.ModelViewSet):
    queryset = EmployeeAssignment.objects.select_related('staff_unit', 'employee', 'staff_unit__division', 'staff_unit__position')
    serializer_class = EmployeeAssignmentSerializer

    def get_permissions(self):
        # Перестановки: Роль-4/5 и Роль-3 в своем управлении
        if self.request.method in permissions.SAFE_METHODS:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()
