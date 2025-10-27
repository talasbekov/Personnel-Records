from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import EmployeeStatusSerializer
from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.auth.permissions.rbac_permissions import (
    IsSystemAdmin,
    IsHrAdmin,
    CanEditOwnDirectorate,
    CanEditOwnDivision,
)

class EmployeeStatusViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления статусами сотрудников.
    """
    queryset = EmployeeStatus.objects.all()
    serializer_class = EmployeeStatusSerializer

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'destroy', 'bulk_create']:
            self.permission_classes = [
                permissions.IsAuthenticated,
                IsSystemAdmin | IsHrAdmin | CanEditOwnDirectorate | CanEditOwnDivision
            ]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [
                permissions.IsAuthenticated,
                IsSystemAdmin | IsHrAdmin | CanEditOwnDirectorate | CanEditOwnDivision
            ]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Массовое создание статусов.
        """
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)
