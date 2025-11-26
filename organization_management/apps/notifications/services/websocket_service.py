"""
Сервис для отправки уведомлений через WebSocket.

Предоставляет универсальную функцию для создания уведомлений в БД
и отправки их через WebSocket подключенным клиентам.
"""
from typing import Optional, Dict, Any
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import logging

from organization_management.apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def send_notification(
    recipient_id: int,
    notification_type: str,
    title: str,
    message: str,
    link: str = "",
    related_object_id: Optional[int] = None,
    related_model: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Notification]:
    """
    Создает уведомление в БД и отправляет его через WebSocket.

    Args:
        recipient_id: ID пользователя-получателя
        notification_type: Тип уведомления (из Notification.NotificationType)
        title: Заголовок уведомления
        message: Текст уведомления
        link: Ссылка (опционально)
        related_object_id: ID связанного объекта (опционально)
        related_model: Название модели связанного объекта (опционально)
        payload: Дополнительные данные JSON (опционально)

    Returns:
        Созданное уведомление или None в случае ошибки
    """
    try:
        # Создаем уведомление в БД
        notification = Notification.objects.create(
            recipient_id=recipient_id,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            related_object_id=related_object_id,
            related_model=related_model,
            payload=payload or {},
        )

        # Отправляем через WebSocket
        channel_layer = get_channel_layer()
        if channel_layer:
            group = f"user_{recipient_id}"
            ws_payload = {
                "id": notification.id,
                "type": notification.notification_type,
                "title": notification.title,
                "message": notification.message,
                "link": notification.link,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
                "payload": notification.payload,
            }

            async_to_sync(channel_layer.group_send)(
                group,
                {
                    "type": "notification_message",
                    "message": ws_payload,
                },
            )
            logger.info(f"Notification sent to user {recipient_id}: {title}")
        else:
            logger.warning("Channel layer not available, notification saved to DB only")

        return notification

    except Exception as e:
        logger.error(f"Error sending notification: {e}", exc_info=True)
        return None


def send_report_ready_notification(report):
    """
    Создает уведомление и отправляет его через Channels пользователю,
    который инициировал генерацию отчета.

    Совместимость со старым API.
    """
    if not report.created_by_id:
        return

    send_notification(
        recipient_id=report.created_by_id,
        notification_type=Notification.NotificationType.REPORT_READY,
        title="Отчет готов",
        message=f"Ваш отчет #{report.id} готов к скачиванию.",
        link=f"/api/reports/{report.id}/download/",
        related_object_id=report.id,
        related_model="Report",
        payload={"report_id": report.id},
    )
