from rest_framework import serializers
from organization_management.apps.audit.models import AuditEntry

class AuditEntrySerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели AuditEntry.
    """
    class Meta:
        model = AuditEntry
        fields = '__all__'
