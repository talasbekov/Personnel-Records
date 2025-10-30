from django.urls import path, include
from rest_framework.routers import DefaultRouter

from organization_management.apps.staffing import views

router = DefaultRouter()
router.register('positions', views.PositionViewSet)
router.register('staffing', views.StaffingViewSet)
router.register('vacancies', views.VacancyViewSet)
router.register('staff-units', views.StaffUnitViewSet)
router.register('assignments', views.EmployeeAssignmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
