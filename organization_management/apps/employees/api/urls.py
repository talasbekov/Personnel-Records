from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.employees.api.views import (
    EmployeeViewSet,
    StaffingUnitViewSet,
    VacancyViewSet,
)

router = DefaultRouter()
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"staffing-units", StaffingUnitViewSet)
router.register(r"vacancies", VacancyViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
