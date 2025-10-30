from rest_framework import serializers

from organization_management.apps.staffing.models import Staffing, Vacancy
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.staffing.models import StaffUnit, EmployeeAssignment
from organization_management.apps.dictionaries.api.serializers import PositionSerializer as DictionaryPositionSerializer


class StaffingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staffing
        fields = '__all__'


class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'


class StaffUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffUnit
        fields = '__all__'

class EmployeeAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAssignment
        fields = '__all__'
