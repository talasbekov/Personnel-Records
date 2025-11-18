from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from organization_management.apps.dictionaries.models import (
    Position,
    Rank
)
from .serializers import (
    PositionSerializer,
    RankSerializer,
    StatusTypeListSerializer
)

class PositionViewSet(viewsets.ModelViewSet):
    """ViewSet для справочника должностей (только GET в API)"""
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'head', 'options']  # Только GET для API

class RankViewSet(viewsets.ModelViewSet):
    """ViewSet для справочника званий (только GET в API)"""
    queryset = Rank.objects.all()
    serializer_class = RankSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'head', 'options']

class StatusTypeViewSet(viewsets.ViewSet):
    """ViewSet для справочника типов статусов (только GET)"""
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """Возвращает список всех доступных типов статусов"""
        serializer = StatusTypeListSerializer({})
        return Response(serializer.data)
