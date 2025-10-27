from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import EmployeeSerializer, StaffingUnitSerializer, VacancySerializer
from organization_management.apps.employees.models import Employee, EmployeeTransferLog, StaffingUnit, Vacancy
from organization_management.apps.auth.permissions.rbac_permissions import IsSystemAdmin, IsHrAdmin
from organization_management.apps.employees.application.services import EmployeeApplicationService
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления сотрудниками.
    Предоставляет CRUD операции и кастомные действия.
    """
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    service = EmployeeApplicationService()

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

    def perform_create(self, serializer):
        self.service.hire_employee(serializer.validated_data)

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """
        Перевод сотрудника в другое подразделение.
        """
        employee = self.get_object()
        division_id = request.data.get('division_id')
        position_id = request.data.get('position_id')
        transfer_date = request.data.get('transfer_date')

        try:
            division = Division.objects.get(id=division_id)
            position = Position.objects.get(id=position_id)
        except (Division.DoesNotExist, Position.DoesNotExist):
            return Response(
                {'error': 'Подразделение или должность не найдены'},
                status=status.HTTP_404_NOT_FOUND
            )

        EmployeeTransferLog.objects.create(
            employee=employee,
            from_division=employee.division,
            to_division=division,
            from_position=employee.position,
            to_position=position,
            transfer_date=transfer_date,
            reason=request.data.get('reason', ''),
            order_number=request.data.get('order_number', '')
        )

        employee.division = division
        employee.position = position
        employee.save()

        return Response({'status': 'сотрудник переведен'})

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """
        Увольнение сотрудника.
        """
        employee = self.get_object()
        employee.employment_status = Employee.EmploymentStatus.FIRED
        employee.dismissal_date = request.data.get('dismissal_date')
        employee.save()
        return Response({'status': 'сотрудник уволен'})

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Получение истории переводов сотрудника.
        """
        employee = self.get_object()
        logs = EmployeeTransferLog.objects.filter(employee=employee)
        # (сериализация логов)
        return Response({'history': []})

class StaffingUnitViewSet(viewsets.ModelViewSet):
    """ViewSet for managing staffing units."""

    queryset = StaffingUnit.objects.all()
    serializer_class = StaffingUnitSerializer

    def get_queryset(self):
        queryset = StaffingUnit.objects.select_related('division', 'position')
        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(division_id=division_id)
        return queryset


class VacancyViewSet(viewsets.ModelViewSet):
    """ViewSet for managing vacancies."""

    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer

    def get_queryset(self):
        queryset = Vacancy.objects.select_related('staffing_unit__division', 'staffing_unit__position')
        is_active = self.request.query_params.get('is_active')
        if is_active:
            queryset = queryset.filter(is_active=(is_active.lower() == 'true'))
        return queryset

    @action(detail=True, methods=['post'])
    def fill(self, request, pk=None):
        vacancy = self.get_object()
        employee_id = request.data.get('employee_id')
        try:
            employee = Employee.objects.get(id=employee_id)
            with transaction.atomic():
                vacancy.is_active = False
                vacancy.save()

                employee.position = vacancy.staffing_unit.position
                employee.division = vacancy.staffing_unit.division
                employee.save()

            return Response({'status': 'вакансия заполнена'})
        except Employee.DoesNotExist:
            return Response({'error': 'Сотрудник не найден'}, status=status.HTTP_404_NOT_FOUND)
