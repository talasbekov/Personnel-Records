from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeStatusViewSet

router = DefaultRouter()
router.register(r'statuses', EmployeeStatusViewSet, basename='employee-status')

urlpatterns = [
    path('', include(router.urls)),
]
