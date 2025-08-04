"""
Serializers for the audit app.

These serializers convert ``AuditLog`` instances into simple JSON
representations for API consumption.  The ``user`` field is read only
and represented by the user's string representation.
"""

from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = AuditLog
        fields = "__all__"