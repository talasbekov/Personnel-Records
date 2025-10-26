from __future__ import annotations
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from organization_management.apps.statuses.models import EmployeeStatusLog
from .serializers import EmployeeStatusLogSerializer
from organization_management.apps.auth.permissions import IsAuthenticated, IsRole1, IsRole2, IsRole3, IsRole4, IsRole5, IsRole6
from organization_management.apps.auth.models import UserRole
from organization_management.apps.statuses.application.services import StatusApplicationService


def _gather_descendant_ids(division):
    """Рекурсивно собрать ID всех потомков подразделения"""
    ids = [division.id]
    for child in division.child_divisions.all():
        ids.extend(_gather_descendant_ids(child))
    return ids


class EmployeeStatusLogViewSet(viewsets.ModelViewSet):
    """ViewSet for managing employee status logs."""

    queryset = EmployeeStatusLog.objects.all()
    serializer_class = EmployeeStatusLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_from', 'created_at']
    ordering = ['-date_from']
    status_service = StatusApplicationService()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsRole3 | IsRole4 | IsRole5 | IsRole6]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return EmployeeStatusLog.objects.none()

        queryset = EmployeeStatusLog.objects.select_related(
            'employee', 'employee__division', 'created_by', 'secondment_division'
        )

        if user.role not in [UserRole.ROLE_1, UserRole.ROLE_4]:
            if not user.division_assignment:
                return EmployeeStatusLog.objects.none()

            if user.role == UserRole.ROLE_2 or (
                user.role == UserRole.ROLE_5 and user.include_child_divisions
            ):
                descendant_ids = _gather_descendant_ids(user.division_assignment)
                queryset = queryset.filter(employee__division_id__in=descendant_ids)
            else:
                queryset = queryset.filter(employee__division=user.division_assignment)

        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_from__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(
                Q(date_to__lte=date_to) | Q(date_to__isnull=True)
            )

        is_auto_copied = self.request.query_params.get('is_auto_copied')
        if is_auto_copied is not None:
            queryset = queryset.filter(is_auto_copied=is_auto_copied.lower() == 'true')

        return queryset

    def perform_create(self, serializer):
        data = serializer.validated_data
        self.status_service.create_status(
            user=self.request.user,
            employee_id=data['employee'].id,
            status=data['status'],
            date_from=data['date_from'],
            date_to=data.get('date_to'),
            comment=data.get('comment')
        )
