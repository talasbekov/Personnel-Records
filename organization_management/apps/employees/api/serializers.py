from rest_framework import serializers
from organization_management.apps.employees.models import Employee, EmployeeTransferLog, StaffingUnit, Vacancy

class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'

class EmployeeTransferLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTransferLog
        fields = '__all__'

class StaffingUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffingUnit
        fields = '__all__'

class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'

class EmployeeBulkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'

class StaffingUnitShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffingUnit
        fields = ('id', 'position', 'quantity')
