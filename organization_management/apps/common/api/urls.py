from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleTypeViewSet

router = DefaultRouter()
router.register(r'role-types', RoleTypeViewSet, basename='role-type')

urlpatterns = [
    path('', include(router.urls)),
]
