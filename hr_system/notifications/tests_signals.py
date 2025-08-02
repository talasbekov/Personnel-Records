import pytest
from django.contrib.auth.models import User
from personnel.models import SecondmentRequest, EmployeeStatusLog, Vacancy, Employee, Division, Position, DivisionType, EmployeeStatusType
from notifications.models import Notification
from django.utils import timezone
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from hr_system.asgi import application

@pytest.mark.django_db
def test_secondment_notification_created(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    user1 = User.objects.create_user(username='testuser1', password='password', is_superuser=True)
    division = Division.objects.create(name='Test Division', division_type=DivisionType.DEPARTMENT)
    position = Position.objects.create(name='Test Position', level=1)
    employee = Employee.objects.create(full_name='Test Employee', division=division, position=position)
    SecondmentRequest.objects.create(
        employee=employee,
        from_division=division,
        to_division=division,
        requested_by=user1,
        date_from=timezone.now().date(),
        reason='Test'
    )
    assert Notification.objects.count() == 1

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_status_update_sends_websocket_message(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    user2 = await database_sync_to_async(User.objects.create_user)(username='testuser2', password='password')
    division = await database_sync_to_async(Division.objects.create)(name='Test Division', division_type=DivisionType.DEPARTMENT)
    position = await database_sync_to_async(Position.objects.create)(name='Test Position', level=1)
    employee = await database_sync_to_async(Employee.objects.create)(full_name='Test Employee', division=division, position=position, user=user2)

    communicator = WebsocketCommunicator(application, f"/ws/notifications/")
    communicator.scope["user"] = user2
    connected, _ = await communicator.connect()
    assert connected

    await database_sync_to_async(EmployeeStatusLog.objects.create)(
        employee=employee,
        status=EmployeeStatusType.ON_LEAVE,
        date_from=timezone.now().date()
    )

    response = await communicator.receive_json_from()
    assert response['message']['type'] == 'status_update'
    assert response['message']['employee_id'] == employee.id

    await communicator.disconnect()
