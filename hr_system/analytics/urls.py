"""
URL configuration for the analytics API.

This module exposes a simple read‑only viewset under the ``/analytics/``
path.  The viewset includes actions for division statistics and KPI
metrics.  Add this module to your project's ``urls.py`` to make the
analytics endpoints available to clients.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AnalyticsViewSet


router = DefaultRouter()
# Register the AnalyticsViewSet without a prefix so that its actions live
# directly under the ``/api/analytics/`` base path.  For example the
# ``division_statistics`` action will be exposed at
# ``/api/analytics/division-statistics/``.
router.register(r"", AnalyticsViewSet, basename="analytics")

urlpatterns = [
    path("", include(router.urls)),
]
