"""
Database models for user notifications.

Notifications are small messages associated with a user that can be
viewed in the UI or delivered via WebSocket.  Each notification
records its type, a human readable title and message, optional payload
data, and whether it has been read.  Notifications are created via
signals in response to events such as status updates, secondment
requests and escalations.
"""

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
    """
    A simple notification model.

    Notifications are addressed to a specific user and carry a type,
    title and message.  Additional structured data can be stored in
    ``payload``.  ``related_object_id`` and ``related_model`` allow
    clients to link back to the originating record.  Notifications may
    be marked as read, storing the timestamp in ``read_at``.
    """

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=20, choices=NotificationType.choices
    )
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

    def __str__(self):
        return f"Notification to {self.recipient} ({self.get_notification_type_display()})"

    def mark_as_read(self):
        """Mark this notification as read if it isn't already."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])