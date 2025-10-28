from rest_framework import viewsets

from organization_management.apps.staffing.models import Staffing, Vacancy
from organization_management.apps.staffing.serializers import StaffingSerializer, VacancySerializer
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.staffing.serializers import PositionSerializer


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer


class StaffingViewSet(viewsets.ModelViewSet):
    queryset = Staffing.objects.all()
    serializer_class = StaffingSerializer


class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer
