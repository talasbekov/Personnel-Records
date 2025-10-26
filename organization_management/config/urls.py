from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from django.conf import settings
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

api_info = openapi.Info(
    title="Organization Management API",
    default_version='v1',
    description="API documentation for the Organization Management system.",
    terms_of_service="https://www.example.com/terms/",
    contact=openapi.Contact(email="support@example.com"),
    license=openapi.License(name="BSD License"),
)

SchemaView = get_schema_view(
    api_info,
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path('swagger<format>/', SchemaView.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', SchemaView.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', SchemaView.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path("api/", include("organization_management.apps.auth.api.urls")),
    path("api/", include("organization_management.apps.divisions.api.urls")),
    path("api/", include("organization_management.apps.employees.api.urls")),
    path("api/", include("organization_management.apps.statuses.api.urls")),
    path("api/", include("organization_management.apps.secondments.api.urls")),
    path("api/", include("organization_management.apps.reports.api.urls")),
    path("api/", include("organization_management.apps.notifications.api.urls")),
    path("api/", include("organization_management.apps.audit.api.urls")),
    path("api/", include("organization_management.apps.dictionaries.api.urls")),
]
