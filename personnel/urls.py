"""
URL configuration for the personnel API.

Registers all viewsets defined in ``personnel.views`` with a DRF router.
These endpoints expose CRUD operations for divisions, positions,
employees, user profiles, secondment requests, status logs, staffing
units and vacancies.  Additional custom actions are available on some
viewsets (see viewset definitions for details).
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DivisionViewSet,
    PositionViewSet,
    EmployeeViewSet,
    UserProfileViewSet,
    SecondmentRequestViewSet,
    EmployeeStatusLogViewSet,
    StaffingUnitViewSet,
    VacancyViewSet,
)

router = DefaultRouter()
router.register(r"divisions", DivisionViewSet, basename="division")
router.register(r"positions", PositionViewSet)
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"user-profiles", UserProfileViewSet)
router.register(r"secondment-requests", SecondmentRequestViewSet)
router.register(r"status-logs", EmployeeStatusLogViewSet)
router.register(r"staffing-units", StaffingUnitViewSet)
router.register(r"vacancies", VacancyViewSet)

urlpatterns = [
    path("", include(router.urls)),
]