from rest_framework import viewsets
from organization_management.apps.audit.models import AuditLog
from .serializers import AuditLogSerializer

class AuditLogViewSet(viewsets.ModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
