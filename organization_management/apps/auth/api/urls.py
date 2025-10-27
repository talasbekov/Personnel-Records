from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, LoginAPIView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('token/', LoginAPIView.as_view(), name='token_obtain_pair'),
    path('', include(router.urls)),
]
