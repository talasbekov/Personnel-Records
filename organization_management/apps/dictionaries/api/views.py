from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from organization_management.apps.dictionaries.models import (
    Position,
    StatusType,
    DismissalReason,
    TransferReason,
    VacancyReason,
    EducationType,
    DocumentType,
    SystemSetting
)
from .serializers import (
    PositionSerializer,
    StatusTypeSerializer,
    DismissalReasonSerializer,
    TransferReasonSerializer,
    VacancyReasonSerializer,
    EducationTypeSerializer,
    DocumentTypeSerializer,
    SystemSettingSerializer
)
from organization_management.apps.auth.permissions import IsRole4, IsRole5

class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated, IsRole4 | IsRole5]

class StatusTypeViewSet(viewsets.ModelViewSet):
    queryset = StatusType.objects.all()
    serializer_class = StatusTypeSerializer
    permission_classes = [IsAuthenticated, IsRole4 | IsRole5]

class DismissalReasonViewSet(viewsets.ModelViewSet):
    queryset = DismissalReason.objects.all()
    serializer_class = DismissalReasonSerializer
    permission_classes = [IsAuthenticated, IsRole4 | IsRole5]

class TransferReasonViewSet(viewsets.ModelViewSet):
    queryset = TransferReason.objects.all()
    serializer_class = TransferReasonSerializer
    permission_classes = [IsAuthenticated, IsRole4 | IsRole5]

class VacancyReasonViewSet(viewsets.ModelViewSet):
    queryset = VacancyReason.objects.all()
    serializer_class = VacancyReasonSerializer
    permission_classes = [IsAuthenticated, IsRole4 | IsRole5]

class EducationTypeViewSet(viewsets.ModelViewSet):
    queryset = EducationType.objects.all()
    serializer_class = EducationTypeSerializer
    permission_classes = [IsAuthenticated, IsRole4 | IsRole5]

class DocumentTypeViewSet(viewsets.ModelViewSet):
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated, IsRole4 | IsRole5]

class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [IsAuthenticated, IsRole4] # Системные настройки - только для админа
