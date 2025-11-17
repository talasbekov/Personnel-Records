from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from organization_management.apps.common.models import Role
from .serializers import RoleTypeSerializer


class RoleTypeViewSet(viewsets.ViewSet):
    """
    ViewSet для получения списка типов ролей из БД

    После миграции на новую систему RBAC, роли теперь хранятся в таблице roles.
    Этот эндпоинт возвращает все активные роли для использования в UI.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RoleTypeSerializer  # Добавляем для drf-spectacular

    def list(self, request):
        """
        Возвращает список всех активных ролей из БД

        Возвращает:
            [
                {'value': 'ROLE_1', 'label': 'Наблюдатель организации'},
                {'value': 'ROLE_2', 'label': 'Наблюдатель департамента'},
                ...
            ]
        """
        # Получаем все активные роли из БД, сортируем по порядку
        db_roles = Role.objects.filter(is_active=True).order_by('sort_order', 'code')

        roles = [
            {'value': role.code, 'label': role.name}
            for role in db_roles
        ]

        serializer = RoleTypeSerializer(roles, many=True)
        return Response(serializer.data)
