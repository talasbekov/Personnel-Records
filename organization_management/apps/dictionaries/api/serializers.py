from typing import List, Dict, Any
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from organization_management.apps.dictionaries.models import (
    Position,
    Rank,
    Feedback
)
from organization_management.apps.statuses.models import EmployeeStatus


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "name", "level"]

class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = '__all__'

class StatusTypeListSerializer(serializers.Serializer):
    status_types = serializers.SerializerMethodField()

    @staticmethod
    @extend_schema_field({'type': 'array', 'items': {'type': 'object', 'properties': {
        'value': {'type': 'string'},
        'label': {'type': 'string'}
    }}})
    def get_status_types(obj) -> List[Dict[str, str]]:
        return [
            {"value": value, "label": label}
            for value, label in EmployeeStatus.StatusType.choices
        ]


class FeedbackSerializer(serializers.ModelSerializer):
    """Сериализатор для обратной связи"""
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = ['id', 'message', 'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at']

    @extend_schema_field({'type': 'string'})
    def get_created_by_name(self, obj) -> str:
        """Возвращает имя пользователя, создавшего обратную связь"""
        if hasattr(obj.created_by, 'employee'):
            employee = obj.created_by.employee
            return f"{employee.last_name} {employee.first_name}"
        return obj.created_by.username
