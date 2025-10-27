from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import DivisionSerializer
from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.models import Employee
from organization_management.apps.employees.api.serializers import EmployeeSerializer
from organization_management.apps.auth.permissions.rbac_permissions import IsSystemAdmin, IsHrAdmin

class DivisionViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления подразделениями.
    Предоставляет CRUD операции и кастомные действия.
    """
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [permissions.IsAuthenticated, IsSystemAdmin | IsHrAdmin]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    @action(detail=True, methods=['get'])
    def employees(self, request, pk=None):
        """
        Получение списка сотрудников для конкретного подразделения.
        """
        division = self.get_object()
        employees = Employee.objects.filter(division=division)
        serializer = EmployeeSerializer(employees, many=True)
        return Response(serializer.data)
