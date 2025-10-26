import jwt
import datetime
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .serializers import LoginSerializer
from drf_yasg.utils import swagger_auto_schema

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

        # Генерация JWT токена
        payload = {
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
            'iat': datetime.datetime.utcnow(),
            'role': user.role
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        return Response({
            'token': token,
            'user_id': user.id,
            'username': user.username,
            'role': user.get_role_display()
        }, status=status.HTTP_200_OK)


from rest_framework import viewsets
from organization_management.apps.auth.models import User
from .serializers import UserSerializer
from organization_management.apps.auth.permissions import IsRole4

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления пользователями.
    Доступно только для системных администраторов (Роль-4).
    """
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsRole4]
