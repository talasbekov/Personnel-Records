"""
URL configuration for the notifications API.

This module registers the ``NotificationViewSet`` with a DRF router
under the root path.  It is included by ``hr_system.urls`` under the
``api/notifications/`` prefix.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet

router = DefaultRouter()
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]