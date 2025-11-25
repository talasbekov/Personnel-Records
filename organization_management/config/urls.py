from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.decorators.cache import cache_page
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),

    # JWT Authentication
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # API Documentation (короткие URL)
    path('docs', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),
    path('redoc', SpectacularRedocView.as_view(url_name='schema'), name='redoc-short'),

    # API Schema (cached to avoid heavy regen on each request):
    path('api/schema/', cache_page(60 * 60)(SpectacularAPIView.as_view()), name='schema'),

    # Optional UI (длинные URL для обратной совместимости):
    path('api/schema/swagger-ui', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API Endpoints:
    path("api/common/", include("organization_management.apps.common.api.urls")),
    path("api/staff_unit/", include("organization_management.apps.staff_unit.urls")),
    path("api/statuses/", include("organization_management.apps.statuses.api.urls")),
    path("api/secondments/", include("organization_management.apps.secondments.api.urls")),
    path("api/reports/", include("organization_management.apps.reports.api.urls")),
    path("api/notifications/", include("organization_management.apps.notifications.api.urls")),
    # path("api/audit/", include("organization_management.apps.audit.api.urls")),
    path("api/dictionaries/", include("organization_management.apps.dictionaries.api.urls")),
    path("api/divisions/", include("organization_management.apps.divisions.api.urls")),
    path("api/employees/", include("organization_management.apps.employees.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)