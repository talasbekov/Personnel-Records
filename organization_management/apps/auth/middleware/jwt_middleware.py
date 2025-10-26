import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from organization_management.apps.auth.models import User

class JWTAuthentication(authentication.BaseAuthentication):
    """
    Кастомный класс аутентификации для проверки JWT токенов.
    """
    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).split()

        if not auth_header or auth_header[0].lower() != b'bearer':
            return None

        if len(auth_header) == 1:
            raise AuthenticationFailed('Недопустимый заголовок авторизации. Токен не предоставлен.')
        elif len(auth_header) > 2:
            raise AuthenticationFailed('Недопустимый заголовок авторизации. Токен содержит пробелы.')

        try:
            token = auth_header[1].decode('utf-8')
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Срок действия токена истек.')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Невалидный токен.')
        except Exception:
            raise AuthenticationFailed('Ошибка при декодировании токена.')

        try:
            user = User.objects.get(pk=payload['user_id'])
        except User.DoesNotExist:
            raise AuthenticationFailed('Пользователь, связанный с токеном, не найден.')

        if not user.is_active:
            raise AuthenticationFailed('Пользователь неактивен.')

        return (user, token)

    def authenticate_header(self, request):
        return 'Bearer'
