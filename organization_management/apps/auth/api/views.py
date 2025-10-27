import jwt
import datetime
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import UserSerializer, LoginSerializer
from organization_management.apps.auth.models import User
from organization_management.apps.auth.permissions.rbac_permissions import IsSystemAdmin

class LoginAPIView(APIView):
    """
    API View для аутентификации пользователя и получения JWT токена.
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

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
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]
