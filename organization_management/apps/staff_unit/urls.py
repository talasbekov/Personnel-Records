from django.urls import path, include
from rest_framework.routers import DefaultRouter

from organization_management.apps.staff_unit import views

router = DefaultRouter()
router.register('positions', views.PositionViewSet)
router.register('staff-units', views.StaffUnitViewSet)
router.register('vacancies', views.VacancyViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
