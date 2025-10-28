from rest_framework import serializers

from organization_management.apps.staffing.models import Staffing, Vacancy
from organization_management.apps.dictionaries.models import Position


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'


class StaffingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staffing
        fields = '__all__'


class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'
