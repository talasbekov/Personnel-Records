from django.urls import path, include
from rest_framework.routers import DefaultRouter
# from .views import EmployeeViewSet # Will be created later

# router = DefaultRouter()
# router.register(r'employees', EmployeeViewSet) # Will be uncommented later

urlpatterns = [
    # path('', include(router.urls)), # Will be uncommented later
    path('test/', lambda request: HttpResponse("Personnel test URL")), # Placeholder
]
