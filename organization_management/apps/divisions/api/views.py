from __future__ import annotations
import io
import csv
import datetime
from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.exceptions import ValidationError
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from organization_management.apps.divisions.models import Division, DivisionType
from .serializers import DivisionSerializer, DivisionDetailSerializer, DivisionTreeSerializer
from organization_management.apps.statuses.api.serializers import BulkStatusUpdateSerializer
from organization_management.apps.employees.models import Employee
from organization_management.apps.statuses.models import EmployeeStatusLog, DivisionStatusUpdate
from organization_management.apps.auth.permissions import IsRole1, IsRole2, IsRole3, IsRole4, IsRole5, IsRole6, IsReadOnly
from organization_management.apps.reports.application.services import generate_personnel_report_docx, generate_personnel_report_xlsx, generate_personnel_report_pdf, get_division_statistics
from organization_management.apps.notifications.models import Notification
from organization_management.apps.audit.models import AuditLog


def _gather_descendant_ids(division):
    """Рекурсивно собрать ID всех потомков подразделения"""
    ids = [division.id]
    for child in division.child_divisions.all():
        ids.extend(_gather_descendant_ids(child))
    return ids


def _build_division_tree(division, include_employees=False):
    """Построить дерево подразделений с опциональным включением сотрудников"""
    data = {
        'id': division.id,
        'name': division.name,
        'code': division.code,
        'division_type': division.division_type,
        'division_type_display': division.get_division_type_display(),
        'children': []
    }

    if include_employees:
        employees = division.employees.filter(is_active=True).select_related('position')
        data['employees'] = [
            {
                'id': emp.id,
                'full_name': emp.full_name,
                'position': emp.position.name,
                'position_level': emp.position.level,
                'current_status': emp.get_current_status()
            }
            for emp in employees.order_by('position__level', 'full_name')
        ]

    for child in division.child_divisions.all().order_by('division_type', 'name'):
        data['children'].append(_build_division_tree(child, include_employees))

    return data


class DivisionViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления подразделениями организации.
    """
    queryset = Division.objects.filter(parent_division__isnull=True)
    serializer_class = DivisionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'division_type', 'created_at']
    ordering = ['division_type', 'name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DivisionDetailSerializer
        elif self.action == 'tree':
            return DivisionTreeSerializer
        return self.serializer_class

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'tree', 'status_summary', 'export']:
            permission_classes = [IsAuthenticated, IsReadOnly | IsRole4 | IsRole5]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'move', 'bulk_import']:
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        elif self.action in ['update_statuses', 'report', 'periodic_report']:
            permission_classes = [IsAuthenticated, IsRole3 | IsRole4 | IsRole5 | IsRole6]
        else:
            permission_classes = [IsAuthenticated]
        return [perm() for perm in permission_classes]

    @action(detail=True, methods=['post'])
    @swagger_auto_schema(
        request_body=BulkStatusUpdateSerializer(many=True)
    )
    def update_statuses(self, request, pk=None):
        division = self.get_object()
        user = request.user

        if not self._can_edit_division_statuses(user, division):
            return Response(
                {'error': 'Недостаточно прав для редактирования статусов'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BulkStatusUpdateSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        created_logs = []
        errors = []

        with transaction.atomic():
            for item in serializer.validated_data:
                try:
                    employee = Employee.objects.get(
                        id=item['employee_id'],
                        division=division,
                        is_active=True
                    )
                    log = EmployeeStatusLog.objects.create(
                        employee=employee,
                        status=item['status'],
                        date_from=item['date_from'],
                        date_to=item.get('date_to'),
                        comment=item.get('comment', ''),
                        created_by=user
                    )
                    created_logs.append(log)
                except Employee.DoesNotExist:
                    errors.append(f"Сотрудник с ID {item['employee_id']} не найден")
                except ValidationError as e:
                    errors.append(f"Ошибка для сотрудника {item['employee_id']}: {str(e)}")

            today = timezone.now().date()
            status_update, created = DivisionStatusUpdate.objects.get_or_create(
                division=division,
                update_date=today,
                defaults={'is_updated': True, 'updated_by': user}
            )
            if not created:
                status_update.mark_as_updated(user)

            self._update_parent_division_status(division, today, user)

        if created_logs:
            self._create_status_update_notifications(division, user)

        return Response({
            'created': len(created_logs),
            'errors': errors
        }, status=status.HTTP_201_CREATED if created_logs else status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def status_summary(self, request):
        date_str = request.query_params.get('date')
        try:
            check_date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты'},
                status=status.HTTP_400_BAD_REQUEST
            )

        divisions = self.get_queryset()
        result = []
        for division in divisions:
            status_update = DivisionStatusUpdate.objects.filter(
                division=division,
                update_date=check_date
            ).first()

            div_data = {
                'id': division.id,
                'name': division.name,
                'division_type': division.division_type,
                'is_updated': status_update.is_updated if status_update else False,
                'updated_at': status_update.updated_at if status_update else None,
                'indicator': 'GREEN' if status_update and status_update.is_updated else 'RED'
            }

            if division.division_type == DivisionType.DEPARTMENT:
                child_statuses = []
                for child in division.child_divisions.filter(division_type=DivisionType.MANAGEMENT):
                    child_update = DivisionStatusUpdate.objects.filter(
                        division=child,
                        update_date=check_date
                    ).first()
                    child_statuses.append({
                        'id': child.id,
                        'name': child.name,
                        'is_updated': child_update.is_updated if child_update else False,
                        'indicator': 'GREEN' if child_update and child_update.is_updated else 'RED'
                    })

                if child_statuses:
                    updated_count = sum(1 for cs in child_statuses if cs['is_updated'])
                    total_count = len(child_statuses)

                    if updated_count == total_count:
                        div_data['indicator'] = 'GREEN'
                    elif updated_count > 0:
                        div_data['indicator'] = 'YELLOW'
                    else:
                        div_data['indicator'] = 'RED'

                    div_data['children'] = child_statuses
                    div_data['updated_children'] = updated_count
                    div_data['total_children'] = total_count

            result.append(div_data)

        return Response(result)

    @action(detail=True, methods=['get'])
    @method_decorator(cache_page(60 * 15))
    def statistics(self, request, pk=None):
        division = self.get_object()
        date_str = request.query_params.get('date')

        try:
            calc_date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stats = get_division_statistics(division, calc_date)
        return Response(stats)

    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        division = self.get_object()
        date_str = request.query_params.get('date')
        if date_str:
            try:
                report_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return Response(
                    {'error': 'Неверный формат даты'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            report_date = timezone.now().date() + datetime.timedelta(days=1)

        file_format = request.query_params.get('format', 'docx').lower()

        if not self._check_all_statuses_updated(division, report_date - datetime.timedelta(days=1)):
            return Response(
                {'error': 'Не все подразделения обновили статусы. Генерация отчета невозможна.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if file_format == 'xlsx':
                file_buffer = generate_personnel_report_xlsx(division, report_date)
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                filename = f'personnel_report_{division.code}_{report_date}.xlsx'
            elif file_format == 'pdf':
                file_buffer = generate_personnel_report_pdf(division, report_date)
                content_type = 'application/pdf'
                filename = f'personnel_report_{division.code}_{report_date}.pdf'
            else:
                file_buffer = generate_personnel_report_docx(division, report_date)
                content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                filename = f'personnel_report_{division.code}_{report_date}.docx'

            AuditLog.objects.create(
                user=request.user,
                action_type='REPORT_GENERATED',
                payload={
                    'division_id': division.id,
                    'report_date': str(report_date),
                    'format': file_format
                }
            )

            response = HttpResponse(
                file_buffer.getvalue(),
                content_type=content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return Response(
                {'error': f'Ошибка генерации отчета: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 5))
    def tree(self, request):
        include_employees = request.query_params.get('include_employees', 'false').lower() == 'true'
        root_divisions = self.get_queryset().filter(parent_division__isnull=True)

        tree_data = []
        for division in root_divisions:
            tree_data.append(_build_division_tree(division, include_employees))

        return Response(tree_data)
