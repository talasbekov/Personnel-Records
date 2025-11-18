from rest_framework import serializers
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
    def get_status_types(obj):
        return [
            {"value": value, "label": label}
            for value, label in EmployeeStatus.StatusType.choices
        ]
