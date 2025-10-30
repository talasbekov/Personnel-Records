from rest_framework import serializers
from organization_management.apps.secondments.models import SecondmentRequest

class SecondmentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecondmentRequest
        fields = '__all__'
