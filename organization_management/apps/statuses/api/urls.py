from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeStatusViewSet, StatusDocumentViewSet

router = DefaultRouter()
router.register(r'statuses', EmployeeStatusViewSet, basename='employee-status')
router.register(r'status-documents', StatusDocumentViewSet, basename='status-document')

urlpatterns = [
    path('', include(router.urls)),
]
