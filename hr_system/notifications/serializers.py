from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    recipient = serializers.StringRelatedField()

    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ('recipient', 'notification_type', 'title', 'message', 'payload', 'related_object_id', 'related_model', 'created_at', 'read_at')
