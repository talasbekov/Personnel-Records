"""
WebSocket consumer for real‑time notifications.

This consumer authenticates the user via Django's session or token
middleware and then subscribes them to a personal group channel.  When
notifications are dispatched to that group the consumer forwards the
payload to the connected WebSocket client.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Only authenticated users can receive notifications
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        self.group_name = f"user_{self.user.id}_notifications"
        # Join the user's notification group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group on disconnect
        group = getattr(self, "group_name", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data):  # pragma: no cover
        # This consumer does not process messages from clients.  Clients
        # should not send messages on this channel.
        pass

    async def notification_message(self, event):
        # Forward a notification payload to the WebSocket client
        message = event.get("message")
        await self.send(text_data=json.dumps({"message": message}))