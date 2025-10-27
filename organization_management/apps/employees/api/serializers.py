from rest_framework import serializers
from organization_management.apps.employees.models import Employee

class EmployeeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Employee.
    """
    class Meta:
        model = Employee
        fields = '__all__'
