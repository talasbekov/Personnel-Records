from rest_framework import serializers

from organization_management.apps.staff_unit.models import Vacancy, StaffUnit
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.dictionaries.api.serializers import PositionSerializer as DictionaryPositionSerializer




class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'


class StaffUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffUnit
        fields = '__all__'
