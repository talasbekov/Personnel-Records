from rest_framework import serializers
from organization_management.apps.employees.models import Employee
from organization_management.apps.dictionaries.api.serializers import RankSerializer

class EmployeeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Employee.
    """
    rank_detail = RankSerializer(source='rank', read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'
