from django.db import models
from django.conf import settings

class AuditEntry(models.Model):
    """Запись в журнале аудита"""

    class ActionType(models.TextChoices):
        CREATE = 'create', 'Создание'
        UPDATE = 'update', 'Изменение'
        DELETE = 'delete', 'Удаление'
        VIEW = 'view', 'Просмотр'
        LOGIN = 'login', 'Вход в систему'
        LOGOUT = 'logout', 'Выход из системы'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices)

    # Информация об объекте
    content_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=500)

    # Детали изменений
    changes = models.JSONField(default=dict, blank=True)

    # Метаданные запроса
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['content_type', 'object_id']),
        ]
