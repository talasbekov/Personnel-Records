from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.divisions.api.views import DivisionViewSet

router = DefaultRouter()
router.register(r"divisions", DivisionViewSet, basename="division")

urlpatterns = [
    path("", include(router.urls)),
]
