"""
Serializer definitions for the notifications API.

Serializers convert ``Notification`` model instances into JSON for
REST API responses.  Only a limited subset of fields are exposed to
clients to prevent modification of system‑generated values.  The
``recipient`` field is read only and presented as a string
representation of the user.
"""

from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    recipient = serializers.StringRelatedField()

    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = (
            "recipient",
            "notification_type",
            "title",
            "message",
            "payload",
            "related_object_id",
            "related_model",
            "created_at",
            "read_at",
        )