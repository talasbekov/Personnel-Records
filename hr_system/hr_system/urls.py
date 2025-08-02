from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from personnel.views import MyTokenObtainPairView  # Our custom view

urlpatterns = [
    path("admin/", admin.site.urls),
    # Personnel app URLs
    path("api/personnel/", include("personnel.urls")),
    path("api/audit/", include("audit.urls")),
    # JWT Token Endpoints
    path("api/token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
]
