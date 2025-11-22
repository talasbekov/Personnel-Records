from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.dictionaries.api.views import (
    PositionViewSet,
    RankViewSet,
    StatusTypeViewSet,
    FeedbackViewSet
)


router = DefaultRouter()
router.register(r"positions", PositionViewSet, basename="positions")
router.register(r"ranks", RankViewSet, basename="ranks")
router.register(r"status_types", StatusTypeViewSet, basename="status-types")
router.register(r"feedback", FeedbackViewSet, basename="feedback")


urlpatterns = [
    path("", include(router.urls)),
]
