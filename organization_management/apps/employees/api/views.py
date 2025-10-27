from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import EmployeeSerializer
from organization_management.apps.employees.models import Employee
from organization_management.apps.auth.permissions.rbac_permissions import IsSystemAdmin, IsHrAdmin

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления сотрудниками.
    Предоставляет CRUD операции и кастомные действия.
    """
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'destroy', 'transfer', 'dismiss']:
            self.permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [permissions.IsAuthenticated, IsSystemAdmin | IsHrAdmin]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """
        Перевод сотрудника в другое подразделение.
        """
        employee = self.get_object()
        division_id = request.data.get('division_id')
        position_id = request.data.get('position_id')
        # ... (логика перевода)
        return Response({'status': 'сотрудник переведен'})

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """
        Увольнение сотрудника.
        """
        employee = self.get_object()
        employee.employment_status = 'fired'
        employee.dismissal_date = request.data.get('dismissal_date')
        employee.save()
        return Response({'status': 'сотрудник уволен'})

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Получение истории переводов сотрудника.
        """
        # ... (логика получения истории)
        return Response({'history': []})
