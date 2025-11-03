from rest_framework import serializers

from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.models import Employee
from organization_management.apps.staff_unit.models import Vacancy, StaffUnit
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.dictionaries.api.serializers import PositionSerializer as DictionaryPositionSerializer



class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'

class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = ["id", "name"]


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "name"]


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id", "first_name", "last_name"]


class StaffUnitSerializer(serializers.ModelSerializer):
    division = DivisionSerializer(read_only=True)
    position = DictionaryPositionSerializer(read_only=True)
    employees = EmployeeSerializer(many=True, read_only=True)
    vacancies = VacancySerializer(many=True, read_only=True)
    children = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StaffUnit
        fields = ["id", "division", "position", "employees", "vacancies", "index", "parent_id", "children"]

    def get_children(self, obj):
        """
        Рекурсивно сериализует дочерние подразделения.
        """
        return StaffUnitSerializer(obj.get_children(), many=True).data
