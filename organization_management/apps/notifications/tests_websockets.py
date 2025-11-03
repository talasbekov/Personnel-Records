import pytest
from channels.testing import WebsocketCommunicator
from django.test import override_settings
from django.contrib.auth.models import User
from organization_management.config.asgi import application
from channels.db import database_sync_to_async

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
async def test_authenticated_user_can_connect():
    user = await database_sync_to_async(User.objects.create_user)(username='testuser1', password='password')
    communicator = WebsocketCommunicator(application, "/ws/notifications/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    await communicator.disconnect()

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
async def test_unauthenticated_user_cannot_connect():
    communicator = WebsocketCommunicator(application, "/ws/notifications/")
    # Simulate an unauthenticated user
    from django.contrib.auth.models import AnonymousUser
    communicator.scope["user"] = AnonymousUser()
    connected, _ = await communicator.connect()
    assert not connected
    # No need to disconnect if not connected, but it's good practice
    try:
        await communicator.disconnect()
    except Exception:
        pass

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
async def test_notification_is_broadcast_to_user():
    user = await database_sync_to_async(User.objects.create_user)(username='testuser2', password='password')
    communicator = WebsocketCommunicator(application, "/ws/notifications/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    # Send a message to the user's group
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f'user_{user.id}_notifications',
        {
            'type': 'notification.message',
            'message': 'Hello, world!'
        }
    )

    response = await communicator.receive_json_from()
    assert response['message'] == 'Hello, world!'

    await communicator.disconnect()
