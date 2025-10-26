from __future__ import annotations
import io
import csv
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from organization_management.apps.employees.models import Employee, EmployeeTransferLog, StaffingUnit, Vacancy
from .serializers import EmployeeSerializer, EmployeeTransferLogSerializer, StaffingUnitSerializer, VacancySerializer, EmployeeBulkSerializer
from organization_management.apps.statuses.models import EmployeeStatusLog
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.notifications.models import Notification
from organization_management.apps.auth.models import UserRole
from organization_management.apps.auth.permissions import IsRole4, IsRole5
from organization_management.apps.employees.tasks import export_employees_to_csv_task, export_employees_to_xlsx_task

class EmployeeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing employees."""

    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['full_name', 'employee_number', 'position__name', 'division__name']
    ordering_fields = ['full_name', 'position', 'division', 'hired_date']
    ordering = ['full_name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_import']:
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        queryset = Employee.objects.select_related('position', 'division')

        if not user.is_staff and user.role != UserRole.ROLE_1:
            division = user.division_assignment
            if division:
                queryset = queryset.filter(
                    Q(division=division) | Q(division__parent_division=division)
                )

        status_param = self.request.query_params.get('status')
        if status_param == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_param == 'fired':
            queryset = queryset.filter(is_active=False)

        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(division_id=division_id)

        position_id = self.request.query_params.get('position_id')
        if position_id:
            queryset = queryset.filter(position_id=position_id)

        return queryset

    @action(detail=False, methods=['post'])
    @swagger_auto_schema(
        request_body=EmployeeBulkSerializer(many=True),
        responses={201: EmployeeBulkSerializer(many=True)}
    )
    def bulk_import(self, request):
        serializer = EmployeeBulkSerializer(data=request.data, many=True)
        if serializer.is_valid():
            employees = serializer.save()

            Notification.objects.create(
                user=request.user,
                type=Notification.NotificationType.BULK_IMPORT_COMPLETE,
                message=f"Успешно импортировано {len(employees)} сотрудников."
            )
            return Response(serializer.data, status=status.HTTP_2_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def export(self, request):
        file_format = request.query_params.get('format', 'csv').lower()
        queryset = self.get_queryset()

        if file_format == 'xlsx':
            task = export_employees_to_xlsx_task.delay(list(queryset.values_list('id', flat=True)))
            return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)
        else:
            task = export_employees_to_csv_task.delay(list(queryset.values_list('id', flat=True)))
            return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        employee = self.get_object()
        transfer_logs = EmployeeTransferLog.objects.filter(employee=employee)
        status_logs = EmployeeStatusLog.objects.filter(employee=employee)

        transfer_serializer = EmployeeTransferLogSerializer(transfer_logs, many=True)
        return Response({
            'transfers': transfer_serializer.data,
        })


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
