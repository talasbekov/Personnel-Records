from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organization_management.apps.secondments.api.views import SecondmentRequestViewSet

router = DefaultRouter()
router.register(r"secondment-requests", SecondmentRequestViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
