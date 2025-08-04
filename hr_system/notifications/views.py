"""
REST API views for notifications.

This viewset provides read‑only access to a user's notifications and an
action to mark notifications as read.  Notifications are ordered
newest first.  Attempts to access notifications for another user are
prevented by the queryset definition.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows notifications to be viewed and marked as read.
    """

    serializer_class = NotificationSerializer

    def get_queryset(self):
        """
        Return only notifications belonging to the authenticated user.
        """
        user = self.request.user
        if not user.is_authenticated:
            return Notification.objects.none()
        return Notification.objects.filter(recipient=user).order_by("-created_at")

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """
        Mark a notification as read.  Only the owner of the notification
        may perform this action.
        """
        notification = self.get_object()
        if notification.recipient != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        notification.mark_as_read()
        return Response(status=status.HTTP_204_NO_CONTENT)