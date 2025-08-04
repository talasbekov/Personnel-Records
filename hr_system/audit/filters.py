"""
Filterset definitions for the audit API.

Uses ``django_filters`` to allow clients to filter audit log entries by
user, action type, content type, object id and timestamp range.
"""

import django_filters
from .models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    class Meta:
        model = AuditLog
        fields = {
            "user": ["exact"],
            "action_type": ["exact"],
            "content_type": ["exact"],
            "object_id": ["exact"],
            "timestamp": ["gte", "lte"],
            "ip_address": ["exact"],
        }