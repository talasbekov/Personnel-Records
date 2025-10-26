from rest_framework import serializers
from organization_management.apps.statuses.models import EmployeeStatusLog, DivisionStatusUpdate, EmployeeStatusType
from organization_management.apps.employees.models import Employee

class EmployeeStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeStatusLog
        fields = '__all__'

class BulkStatusUpdateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=EmployeeStatusType.choices)
    date_from = serializers.DateField()
    date_to = serializers.DateField(required=False)
    comment = serializers.CharField(required=False)
