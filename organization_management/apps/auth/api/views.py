from __future__ import annotations
import jwt
import datetime
from django.conf import settings
from rest_framework import status, viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_yasg.utils import swagger_auto_schema

from organization_management.apps.auth.models import User, UserRole
from organization_management.apps.auth.permissions import IsRole4
from organization_management.apps.employees.models import Employee
from .serializers import LoginSerializer, UserSerializer


class LoginAPIView(APIView):
    """
    API View для аутентификации пользователя и получения JWT токена.
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @swagger_auto_schema(request_body=LoginSerializer)
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        payload = {
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
            'iat': datetime.datetime.utcnow(),
            'role': user.role,
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        return Response({
            'token': token,
            'user_id': user.id,
            'username': user.username,
            'role': user.get_role_display(),
        }, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления пользователями.
    Доступно только для системных администраторов (Роль-4).
    """
    queryset = User.objects.select_related('division_assignment').order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsRole4]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['username', 'role']
    ordering = ['username']

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(division_assignment_id=division_id)

        return queryset
