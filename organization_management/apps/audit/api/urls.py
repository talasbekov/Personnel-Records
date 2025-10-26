from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.audit.api.views import AuditLogViewSet

router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
]
