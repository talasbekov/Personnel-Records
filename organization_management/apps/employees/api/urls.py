from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeViewSet, StaffingUnitViewSet, VacancyViewSet

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'staffing-units', StaffingUnitViewSet, basename='staffing-unit')
router.register(r'vacancies', VacancyViewSet, basename='vacancy')

urlpatterns = [
    path('', include(router.urls)),
]
