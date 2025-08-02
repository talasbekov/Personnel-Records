from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class NotificationType(models.TextChoices):
    SECONDMENT = "SECONDMENT", _("Secondment")
    STATUS_UPDATE = "STATUS_UPDATE", _("Status Update")
    RETURN_REQUEST = "RETURN_REQUEST", _("Return Request")
    VACANCY_CREATED = "VACANCY_CREATED", _("Vacancy Created")
    TRANSFER = "TRANSFER", _("Transfer")
    ESCALATION = "ESCALATION", _("Escalation")

class Notification(models.Model):
    """Уведомления"""
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_model = models.CharField(max_length=50, blank=True, null=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])
