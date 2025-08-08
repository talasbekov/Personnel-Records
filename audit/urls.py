"""
URL configuration for the audit API.

Registers the ``AuditLogViewSet`` on the ``logs/`` endpoint.  This file
is included by ``hr_system.urls`` under the ``api/audit/`` prefix.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditLogViewSet

router = DefaultRouter()
router.register(r"logs", AuditLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
]