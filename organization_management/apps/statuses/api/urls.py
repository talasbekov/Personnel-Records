from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.statuses.api.views import EmployeeStatusLogViewSet

router = DefaultRouter()
router.register(r"status-logs", EmployeeStatusLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
