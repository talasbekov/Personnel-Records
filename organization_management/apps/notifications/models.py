from django.db import models
from django.conf import settings

class Notification(models.Model):
    """Модель уведомления"""

    class NotificationType(models.TextChoices):
        STATUS_CHANGED = 'status_changed', 'Изменение статуса'
        SECONDMENT_REQUEST = 'secondment_request', 'Запрос на прикомандирование'
        SECONDMENT_APPROVED = 'secondment_approved', 'Прикомандирование одобрено'
        SECONDMENT_REJECTED = 'secondment_rejected', 'Прикомандирование отклонено'
        REPORT_READY = 'report_ready', 'Отчет готов'
        EMPLOYEE_HIRED = 'employee_hired', 'Прием на работу'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)

    # Дополнительные поля для связи с объектами и метаданных
    related_object_id = models.IntegerField(null=True, blank=True, help_text="ID связанного объекта")
    related_model = models.CharField(max_length=100, blank=True, help_text="Название модели связанного объекта")
    payload = models.JSONField(null=True, blank=True, help_text="Дополнительные данные в формате JSON")

    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True, help_text="Дата и время прочтения")

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
