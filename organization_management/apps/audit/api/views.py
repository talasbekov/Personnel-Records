from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import AuditEntrySerializer
from organization_management.apps.audit.models import AuditEntry


class AuditEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра журнала аудита.
    """
    queryset = AuditEntry.objects.all()
    serializer_class = AuditEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Экспорт логов аудита.
        """
        # (логика экспорта)
        return Response({'status': 'exporting logs...'})
