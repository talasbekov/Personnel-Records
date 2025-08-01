from rest_framework import viewsets, permissions
from .models import Division, Position, Employee, UserProfile, EmployeeStatusLog
from .serializers import (
    DivisionSerializer,
    PositionSerializer,
    EmployeeSerializer,
    UserProfileSerializer,
    MyTokenObtainPairSerializer,  # Added by subtask
    # EmployeeStatusLogSerializer
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView as OriginalTokenObtainPairView,
)  # Added by subtask


# TODO: Implement proper permissions later based on roles
class DivisionViewSet(viewsets.ModelViewSet):
    queryset = Division.objects.all().prefetch_related("child_divisions")
    serializer_class = DivisionSerializer
    permission_classes = [permissions.IsAuthenticated]


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all().select_related("position", "division")
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all().select_related("user", "division_assignment")
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]


# class EmployeeStatusLogViewSet(viewsets.ModelViewSet):
# queryset = EmployeeStatusLog.objects.all()
# serializer_class = EmployeeStatusLogSerializer
# permission_classes = [permissions.IsAuthenticated] # Placeholder


# Custom Token View to use the custom serializer (appended by subtask)
class MyTokenObtainPairView(OriginalTokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
