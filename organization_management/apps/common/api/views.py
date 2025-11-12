from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from organization_management.apps.common.models import UserRole
from .serializers import RoleTypeSerializer


class RoleTypeViewSet(viewsets.ViewSet):
    """
    ViewSet 4;O ?>;CG5=8O A?8A:0 B8?>2 @>;59
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """
        >72@0I05B A?8A>: 2A5E 4>ABC?=KE B8?>2 @>;59
        """
        roles = [
            {'value': choice[0], 'label': choice[1]}
            for choice in UserRole.RoleType.choices
        ]
        serializer = RoleTypeSerializer(roles, many=True)
        return Response(serializer.data)