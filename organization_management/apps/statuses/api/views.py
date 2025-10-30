from rest_framework import viewsets, permissions
from django.db import models
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import EmployeeStatusSerializer
from organization_management.apps.statuses.models import EmployeeStatus

from organization_management.apps.divisions.models import Division

class EmployeeStatusViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления статусами сотрудников.
    """
    queryset = EmployeeStatus.objects.all()
    serializer_class = EmployeeStatusSerializer

    def _get_department_root(self, division: Division) -> Division:
        node = division
        while node.parent and node.division_type != Division.DivisionType.DEPARTMENT:
            node = node.parent
        return node

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if not user.is_authenticated:
            return qs.none()
        role = getattr(user, "role", None)
        if role in (user.RoleType.SYSTEM_ADMIN, user.RoleType.OBSERVER_ORG):  # type: ignore[attr-defined]
            return qs
        if not user.division_id:
            return qs.none()
        if role == user.RoleType.HR_ADMIN:  # type: ignore[attr-defined]
            allowed = user.division.get_descendants(include_self=True)
        else:
            dept_root = self._get_department_root(user.division)
            allowed = dept_root.get_descendants(include_self=True)
        return qs.filter(employee__division_id__in=allowed.values_list("id", flat=True))

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'destroy', 'bulk_create']:
            self.permission_classes = [
                permissions.IsAuthenticated
            ]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [
                permissions.IsAuthenticated
            ]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Текущий статус сотрудника на дату.
        Параметры: employee_id (обяз.), date (YYYY-MM-DD, опционально, по умолчанию сегодня).
        """
        from django.utils import timezone
        from datetime import date as _date

        employee_id = request.query_params.get('employee_id')
        date_str = request.query_params.get('date')
        if not employee_id:
            return Response({'detail': 'employee_id is required'}, status=400)
        try:
            target_date = _date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response({'detail': 'invalid date'}, status=400)

        qs = self.get_queryset().filter(
            employee_id=employee_id,
            start_date__lte=target_date,
        ).filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=target_date))

        instance = qs.order_by('-start_date').first()
        if not instance:
            return Response({}, status=200)
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        История статусов сотрудника.
        Параметры: employee_id (обяз.).
        """
        employee_id = request.query_params.get('employee_id')
        if not employee_id:
            return Response({'detail': 'employee_id is required'}, status=400)
        qs = self.get_queryset().filter(employee_id=employee_id).order_by('-start_date')
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Массовое создание статусов.
        """
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)
