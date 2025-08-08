"""
Enhanced WebSocket consumer for real‑time notifications.

This consumer implements basic per‑user WebSocket notifications with
rate‑limiting to avoid flooding the client.  The original implementation
simply forwarded each message immediately; here we add a one‑second
throttle so that no more than one message is sent per second.  If
multiple notifications arrive within that window, only the most recent
payload is delivered once the interval elapses.

Note: this module is designed to replace ``hr_system/notifications/consumers.py`` in
the original project.  To use it, copy the contents into that file.
"""

import json
import asyncio
import time
from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer with simple throttling and message coalescing."""

    def __init__(self, *args, **kwargs):  # pragma: no cover
        super().__init__(*args, **kwargs)
        # Timestamp of the last message sent to the client
        self._last_send_ts: float = 0.0
        # Buffer for the most recent pending message; only the latest
        # notification received during the throttle window will be sent.
        self._pending_message: dict[str, str] | None = None
        # Lock to prevent concurrent flushes
        self._flush_lock = asyncio.Lock()

    async def connect(self):  # pragma: no cover
        # Only authenticated users can receive notifications
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        self.group_name = f"user_{self.user.id}_notifications"
        # Join the user's notification group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):  # pragma: no cover
        # Leave the group on disconnect
        group = getattr(self, "group_name", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data):  # pragma: no cover
        # Clients should not send messages on this channel.
        pass

    async def notification_message(self, event):
        """Handle incoming notification from the channel layer.

        If a message arrives less than one second after the previous
        dispatch, it is stored in a buffer.  After the throttle window
        expires the latest buffered message will be sent and the buffer
        cleared.
        """
        message = event.get("message")
        now = time.monotonic()
        # Determine if we should send immediately or buffer
        if now - self._last_send_ts >= 1.0:
            # Send immediately
            await self.send(text_data=json.dumps({"message": message}))
            self._last_send_ts = now
            self._pending_message = None
        else:
            # Replace any pending message with the new one
            self._pending_message = {"message": message}
            # Schedule a flush if not already scheduled
            async with self._flush_lock:
                # Only schedule if this is the first buffered message
                await asyncio.sleep(1.0 - (now - self._last_send_ts))
                # Flush the latest pending message, if any
                if self._pending_message:
                    await self.send(text_data=json.dumps(self._pending_message))
                    self._last_send_ts = time.monotonic()
                    self._pending_message = None