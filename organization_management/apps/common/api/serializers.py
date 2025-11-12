from rest_framework import serializers

from organization_management.apps.common.models import UserRole


class RoleTypeSerializer(serializers.Serializer):
    """Сериализатор для типов ролей (RoleType choices)"""
    value = serializers.CharField()
    label = serializers.CharField()

    class Meta:
        fields = ['value', 'label']