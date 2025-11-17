from typing import Optional
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from organization_management.apps.notifications.models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для управления уведомлениями текущего пользователя.

    Предоставляет доступ только к уведомлениям текущего пользователя.
    Поддерживает пометку уведомлений как прочитанных.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Возвращает список всех уведомлений для текущего пользователя.
        """
        return Notification.objects.filter(recipient=self.request.user)

    @extend_schema(
        summary="Получить непрочитанные уведомления",
        description="Возвращает список всех непрочитанных уведомлений текущего пользователя"
    )
    @action(detail=False, methods=['get'])
    def unread(self, request: Request) -> Response:
        """
        Получение списка непрочитанных уведомлений.
        """
        queryset = self.get_queryset().filter(is_read=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Пометить уведомление как прочитанное",
        description="Помечает указанное уведомление как прочитанное",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID уведомления'
            )
        ]
    )
    @action(detail=True, methods=['post'])
    def mark_read(self, request: Request, pk: Optional[int] = None) -> Response:
        """
        Пометить уведомление как прочитанное.

        Args:
            request: HTTP запрос
            pk: ID уведомления

        Returns:
            Response с кодом 204 при успехе
        """
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Пометить все уведомления как прочитанные",
        description="Помечает все уведомления текущего пользователя как прочитанные"
    )
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request: Request) -> Response:
        """
        Пометить все уведомления как прочитанные.

        Args:
            request: HTTP запрос

        Returns:
            Response с кодом 204 при успехе
        """
        self.get_queryset().update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
