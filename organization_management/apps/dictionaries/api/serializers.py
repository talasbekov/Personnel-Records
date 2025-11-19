from typing import List, Dict, Any
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from organization_management.apps.dictionaries.models import (
    Position,
    Rank
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
