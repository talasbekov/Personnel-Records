# models.py
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class AuditLog(models.Model):
    """Журнал аудита"""
    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("STATUS_CHANGE", "Status Change"),
        ("TRANSFER", "Transfer"),
        ("SECONDMENT", "Secondment"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("REPORT_GENERATED", "Report Generated"),
        ("UNAUTHORIZED_ACCESS", "Unauthorized Access"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)

    # Generic relation to the target object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target_object = GenericForeignKey("content_type", "object_id")

    payload = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp", "user"]),
            models.Index(fields=["action_type"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"Action: {self.get_action_type_display()} by {self.user} at {self.timestamp}"