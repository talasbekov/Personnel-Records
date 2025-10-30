import json
from organization_management.apps.audit.models import AuditEntry

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.log_request(request, response)
        return response

    def log_request(self, request, response):
        """
        Логирование запроса.
        """
        user = request.user if request.user.is_authenticated else None

        # Определяем action_type (упрощенная логика)
        action_type = ''
        if response.status_code >= 200 and response.status_code < 300:
            if request.method == 'POST':
                action_type = AuditEntry.ActionType.CREATE
            elif request.method in ['PUT', 'PATCH']:
                action_type = AuditEntry.ActionType.UPDATE
            elif request.method == 'DELETE':
                action_type = AuditEntry.ActionType.DELETE
            elif request.method == 'GET':
                action_type = AuditEntry.ActionType.VIEW

        # Пропускаем незначащие запросы
        if not action_type or 'admin' in request.path:
            return

        try:
            object_repr = response.data.get('repr', str(response.data))[:500] if hasattr(response, 'data') else ''
        except (AttributeError, TypeError):
            object_repr = ''

        changes = {}
        if hasattr(request, 'data'):
            try:
                changes = json.dumps(request.data)
            except (TypeError, ValueError):
                changes = {}

        AuditEntry.objects.create(
            user=user,
            action_type=action_type,
            object_repr=object_repr,
            changes=changes,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    def get_client_ip(self, request):
        """
        Получение IP-адреса клиента.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
