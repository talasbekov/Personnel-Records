from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.auth.api.views import UserProfileViewSet, MyTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView


router = DefaultRouter()
router.register(r"user-profiles", UserProfileViewSet)

urlpatterns = [
    path("token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
]
