from rest_framework import serializers
from organization_management.apps.secondments.models import SecondmentRequest
from organization_management.apps.employees.models import Employee

class SecondmentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecondmentRequest
        fields = '__all__'
