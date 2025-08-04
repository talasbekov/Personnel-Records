"""
Models for storing audit log entries.

The ``AuditLog`` model captures high‑level CRUD and custom events in the
system, including the acting user (if any), a generic foreign key to
the affected object and a JSON payload for arbitrary metadata (such as
field diffs).  The model also records request metadata like IP
address and user agent for forensic purposes.
"""

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class AuditLog(models.Model):
    """
    A record of an action performed in the system.

    Actions include CRUD operations on API endpoints and custom events
    such as status changes or report generation.  A generic relation
    allows linking the log entry to any model instance.
    """

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
        ("ESCALATION", "Escalation"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)

    # Generic relation to the target object
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
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