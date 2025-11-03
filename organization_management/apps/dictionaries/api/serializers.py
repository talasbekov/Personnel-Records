from rest_framework import serializers
from organization_management.apps.dictionaries.models import (
    Position,
    Rank,
    StatusType,
    DismissalReason,
    TransferReason,
    VacancyReason,
    EducationType,
    DocumentType,
    SystemSetting,
)

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'

class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = '__all__'

class StatusTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusType
        fields = '__all__'

class DismissalReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = DismissalReason
        fields = '__all__'

class TransferReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferReason
        fields = '__all__'

class VacancyReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacancyReason
        fields = '__all__'

class EducationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EducationType
        fields = '__all__'

class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = '__all__'

class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = '__all__'
