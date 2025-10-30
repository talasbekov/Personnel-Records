import uuid

from rest_framework import serializers
from organization_management.apps.reports.models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"

    def create(self, validated_data):
        # Генерируем уникальный job_id сразу при создании задания
        if not validated_data.get("job_id"):
            validated_data["job_id"] = uuid.uuid4().hex
        return super().create(validated_data)
