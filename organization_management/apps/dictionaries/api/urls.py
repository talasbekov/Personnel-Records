from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PositionViewSet,
    StatusTypeViewSet,
    DismissalReasonViewSet,
    TransferReasonViewSet,
    VacancyReasonViewSet,
    EducationTypeViewSet,
    DocumentTypeViewSet,
    SystemSettingViewSet
)

router = DefaultRouter()
router.register(r'positions', PositionViewSet)
router.register(r'status-types', StatusTypeViewSet)
router.register(r'dismissal-reasons', DismissalReasonViewSet)
router.register(r'transfer-reasons', TransferReasonViewSet)
router.register(r'vacancy-reasons', VacancyReasonViewSet)
router.register(r'education-types', EducationTypeViewSet)
router.register(r'document-types', DocumentTypeViewSet)
router.register(r'system-settings', SystemSettingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
