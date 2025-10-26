from rest_framework import serializers
from organization_management.apps.reports.models import Report

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = '__all__'
