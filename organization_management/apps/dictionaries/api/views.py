from rest_framework import viewsets, permissions

from organization_management.apps.dictionaries.models import (
    Position,
    Rank
)
from .serializers import (
    PositionSerializer,
    RankSerializer
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
