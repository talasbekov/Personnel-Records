import django_filters
from .models import AuditLog

class AuditLogFilter(django_filters.FilterSet):
    class Meta:
        model = AuditLog
        fields = {
            'user': ['exact'],
            'action_type': ['exact'],
            'content_type': ['exact'],
            'object_id': ['exact'],
            'timestamp': ['gte', 'lte'],
            'ip_address': ['exact'],
        }
