# hr_system/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from rest_framework import permissions
from django.conf import settings  # <-- добавили
from ..personnel.views import MyTokenObtainPairView  # <-- фикс относительного импорта

from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django_filters import rest_framework as filters

filters.DjangoFilterBackend.get_schema_operation_parameters = lambda self, view: []

api_info = openapi.Info(
    title="Personnel Records API",
    default_version='v1',
    description="Документация API для системы управления персоналом",
    terms_of_service="https://www.example.com/terms/",
    contact=openapi.Contact(email="support@example.com"),
    license=openapi.License(name="BSD License"),
)

SchemaView = get_schema_view(
    info=api_info,
    public=True,
    permission_classes=(permissions.AllowAny,),
    url=getattr(settings, "PUBLIC_BASE_URL", None),  # <-- ключевая строка
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path('swagger<format>/', SchemaView.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', SchemaView.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', SchemaView.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path("api/personnel/", include("personnel.urls")),
    path("api/audit/", include("audit.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/analytics/", include("analytics.urls")),
]
