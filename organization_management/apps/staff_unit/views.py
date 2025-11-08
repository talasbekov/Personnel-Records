from rest_framework import viewsets, permissions

from organization_management.apps.staff_unit.models import Vacancy, StaffUnit
from organization_management.apps.staff_unit.serializers import (
    VacancySerializer,
    StaffUnitSerializer,
)
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.dictionaries.api.serializers import PositionSerializer
from organization_management.apps.common.drf_permissions import (
    RoleBasedPermission,
    CanViewVacancies,
    CanCreateVacancy,
    CanEditVacancy,
    CanViewStaffingTable,
    CanManageStaffingTable
)
from organization_management.apps.common.rbac import get_user_scope_queryset


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()


class VacancyViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления вакансиями с проверкой прав на основе ролей
    """
    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer

    # Маппинг actions на требуемые права
    permission_map = {
        'list': 'view_vacancies',
        'retrieve': 'view_vacancies',
        'create': 'create_vacancy',
        'update': 'edit_vacancy',
        'partial_update': 'edit_vacancy',
        'destroy': 'close_vacancy',
    }

    def get_permissions(self):
        """Динамическое определение permissions на основе action"""
        if self.action in ['create']:
            return [permissions.IsAuthenticated(), CanCreateVacancy()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), CanEditVacancy()]
        else:
            return [permissions.IsAuthenticated(), CanViewVacancies()]

    def get_queryset(self):
        """Фильтрация queryset по области видимости пользователя"""
        user = self.request.user

        # Суперпользователь видит всё
        if user.is_superuser:
            return Vacancy.objects.all()

        # Используем RBAC engine для фильтрации
        return get_user_scope_queryset(user, Vacancy)


class StaffUnitViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления штатным расписанием с проверкой прав на основе ролей
    """
    queryset = StaffUnit.objects.all()
    serializer_class = StaffUnitSerializer

    # Маппинг actions на требуемые права
    permission_map = {
        'list': 'view_staffing_table',
        'retrieve': 'view_staffing_table',
        'create': 'create_staffing_position',
        'update': 'edit_staffing_position',
        'partial_update': 'edit_staffing_position',
        'destroy': 'delete_staffing_position',
    }

    def get_permissions(self):
        """Динамическое определение permissions на основе action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), CanManageStaffingTable()]
        else:
            return [permissions.IsAuthenticated(), CanViewStaffingTable()]

    def get_queryset(self):
        """Фильтрация queryset по области видимости пользователя"""
        user = self.request.user

        # Суперпользователь видит всё
        if user.is_superuser:
            return StaffUnit.objects.all()

        # Используем RBAC engine для фильтрации
        return get_user_scope_queryset(user, StaffUnit)
