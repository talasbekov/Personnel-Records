from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditEntryViewSet

router = DefaultRouter()
router.register(r'audit', AuditEntryViewSet, basename='audit')

urlpatterns = [
    path('', include(router.urls)),
]
