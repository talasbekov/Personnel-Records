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

from rest_framework import permissions
from personnel.views import MyTokenObtainPairView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
   openapi.Info(
      title="Personnel API",
      default_version='v1',
      description="Документация по API системы учёта персонала",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="your@email.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
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