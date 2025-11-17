from rest_framework import serializers
from organization_management.apps.dictionaries.models import (
    Position,
    Rank
)

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "name", "level"]

class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = '__all__'
