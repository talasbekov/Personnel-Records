"""
URL routing for WebSocket notifications.

Defines the URL patterns that are used to route incoming WebSocket
connections to the appropriate consumer.  This module is referenced in
``hr_system.asgi`` when constructing the Channels application.
"""

from django.urls import re_path
from . import consumers


websocket_urlpatterns = [
    re_path(r"^ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
]