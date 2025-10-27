from rest_framework import serializers
from organization_management.apps.employees.models import Employee, StaffingUnit, Vacancy

class EmployeeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Employee.
    """
    class Meta:
        model = Employee
        fields = '__all__'

class StaffingUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffingUnit
        fields = '__all__'

class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'
