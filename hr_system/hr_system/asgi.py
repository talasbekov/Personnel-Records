"""
ASGI entrypoint for the HR system.

Defines the protocol type router to dispatch HTTP requests to Django's
ASGI application and WebSocket connections to the notifications
consumer via Channels.  ``AuthMiddlewareStack`` ensures that WebSocket
connections are associated with a Django session or JWT token so that
authenticated users receive their own notifications.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import notifications.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hr_system.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(notifications.routing.websocket_urlpatterns)
        ),
    }
)