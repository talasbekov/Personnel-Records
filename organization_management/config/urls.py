from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # API Schema:
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # API Endpoints:
    path("api/auth/", include("organization_management.apps.auth.api.urls")),
    path("api/divisions/", include("organization_management.apps.divisions.api.urls")),
    path("api/employees/", include("organization_management.apps.employees.api.urls")),
    path("api/statuses/", include("organization_management.apps.statuses.api.urls")),
    path("api/secondments/", include("organization_management.apps.secondments.api.urls")),
    path("api/reports/", include("organization_management.apps.reports.api.urls")),
    path("api/notifications/", include("organization_management.apps.notifications.api.urls")),
    path("api/audit/", include("organization_management.apps.audit.api.urls")),
    path("api/dictionaries/", include("organization_management.apps.dictionaries.api.urls")),
    path("api/staffing/", include("organization_management.apps.staffing.urls")),
]
