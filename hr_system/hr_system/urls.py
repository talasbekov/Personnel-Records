"""
Root URL configuration for the HR system project.

This file wires up the REST API endpoints for the personnel,
notifications and audit apps as well as JWT authentication routes.
It is included by Django at startup and referenced by the ASGI/WSGI
entrypoints.
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from personnel.views import MyTokenObtainPairView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/personnel/", include("personnel.urls")),
    path("api/audit/", include("audit.urls")),
    path("api/notifications/", include("notifications.urls")),
    # JWT endpoints
    path(
        "api/token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    path(
        "api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    path(
        "api/token/verify/", TokenVerifyView.as_view(), name="token_verify"
    ),
    # Analytics endpoints
    path("api/analytics/", include("analytics.urls")),
]