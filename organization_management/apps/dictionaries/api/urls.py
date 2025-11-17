from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.dictionaries.api.views import (
    PositionViewSet,
    RankViewSet
)

router = DefaultRouter()
router.register(r"positions", PositionViewSet)
router.register(r"ranks", RankViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
