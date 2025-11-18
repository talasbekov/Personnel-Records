from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.divisions.api.views import DivisionViewSet, DivisionTreeViewSet

router = DefaultRouter()
# router.register(r"divisions", DivisionViewSet, basename="division")
router.register(r"divisions_tree", DivisionTreeViewSet, basename="division-tree")

urlpatterns = [
    path("", include(router.urls)),
]
