from rest_framework import serializers
from organization_management.apps.statuses.models import EmployeeStatus

class EmployeeStatusSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели EmployeeStatus.
    """
    class Meta:
        model = EmployeeStatus
        fields = '__all__'
