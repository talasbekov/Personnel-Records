from rest_framework import viewsets
from organization_management.apps.dictionaries.models import (
    Position,
    StatusType,
    DismissalReason,
    TransferReason,
    VacancyReason,
    EducationType,
    DocumentType,
    SystemSetting,
)
from .serializers import (
    PositionSerializer,
    StatusTypeSerializer,
    DismissalReasonSerializer,
    TransferReasonSerializer,
    VacancyReasonSerializer,
    EducationTypeSerializer,
    DocumentTypeSerializer,
    SystemSettingSerializer,
)

class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

class StatusTypeViewSet(viewsets.ModelViewSet):
    queryset = StatusType.objects.all()
    serializer_class = StatusTypeSerializer

class DismissalReasonViewSet(viewsets.ModelViewSet):
    queryset = DismissalReason.objects.all()
    serializer_class = DismissalReasonSerializer

class TransferReasonViewSet(viewsets.ModelViewSet):
    queryset = TransferReason.objects.all()
    serializer_class = TransferReasonSerializer

class VacancyReasonViewSet(viewsets.ModelViewSet):
    queryset = VacancyReason.objects.all()
    serializer_class = VacancyReasonSerializer

class EducationTypeViewSet(viewsets.ModelViewSet):
    queryset = EducationType.objects.all()
    serializer_class = EducationTypeSerializer

class DocumentTypeViewSet(viewsets.ModelViewSet):
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer

class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
