from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.reports.api.views import ReportViewSet

router = DefaultRouter()
router.register(r"reports", ReportViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
