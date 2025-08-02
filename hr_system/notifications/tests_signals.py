import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from personnel.models import (
    SecondmentRequest,
    EmployeeStatusLog,
    Vacancy,
    Employee,
    Division,
    Position,
    DivisionType,
    EmployeeStatusType,
)
from notifications.models import Notification
from personnel.models import UserProfile, UserRole

# Optional imports for websocket test
try:
    from channels.testing import WebsocketCommunicator
    from hr_system.asgi import application
    from asgiref.sync import sync_to_async
    _has_channels = True
except ImportError:
    _has_channels = False


@pytest.mark.django_db
def test_secondment_notification_created():
    user1 = User.objects.create_user(username="testuser1", password="password", is_superuser=True)
    division = Division.objects.create(name="Test Division", division_type=DivisionType.DEPARTMENT)
    position = Position.objects.create(name="Test Position", level=1)
    employee = Employee.objects.create(full_name="Test Employee", division=division, position=position)
    # Ensure at least one superuser exists for recipient fallback
    SecondmentRequest.objects.create(
        employee=employee,
        from_division=division,
        to_division=division,
        requested_by=user1,
        date_from=timezone.now().date(),
        reason="Test",
    )
    # One notification for the secondment request (recipient is superuser)
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_status_update_notification_created():
    user = User.objects.create_user(username="testuser2", password="password")
    UserProfile.objects.create(user=user, role=UserRole.ROLE_4)
    division = Division.objects.create(name="Test Division", division_type=DivisionType.DEPARTMENT)
    position = Position.objects.create(name="Test Position", level=1)
    employee = Employee.objects.create(
        full_name="Test Employee", division=division, position=position, user=user
    )
    EmployeeStatusLog.objects.create(
        employee=employee,
        status=EmployeeStatusType.ON_LEAVE,
        date_from=timezone.now().date(),
    )
    # Notification to the employee about status change
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_vacancy_notification_created():
    user1 = User.objects.create_user(username="testuser1", password="password", is_superuser=True)
    division = Division.objects.create(name="Test Division", division_type=DivisionType.DEPARTMENT)
    position = Position.objects.create(name="Test Position", level=1)
    staffing_unit = division.staffing_units.create(position=position, quantity=1)
    Vacancy.objects.create(
        staffing_unit=staffing_unit,
        title="New Test Vacancy",
        created_by=user1,
    )
    # Notification to the creator
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_employee_create_update_delete_notifications():
    # Create user and employee
    user = User.objects.create_user(username="testuser2", password="password")
    division = Division.objects.create(name="Test Division", division_type=DivisionType.DEPARTMENT)
    position = Position.objects.create(name="Test Position", level=1)
    employee = Employee.objects.create(
        full_name="Test Employee", division=division, position=position, user=user
    )
    # Creation notification (if logic emits on creation)
    initial_count = Notification.objects.count()

    # Update employee
    employee.full_name = "Updated Name"
    employee.save()
    after_update = Notification.objects.count()
    assert after_update >= initial_count + 1

    # Delete employee
    employee.delete()
    after_delete = Notification.objects.count()
    assert after_delete >= after_update + 1


@pytest.mark.skipif(not _has_channels, reason="Channels not installed, skipping websocket test")
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_status_update_sends_websocket_message(settings):
    # Use in-memory channel layer for test
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    user = await sync_to_async(User.objects.create_user)(
        username="testuser_ws", password="password"
    )
    division = await sync_to_async(Division.objects.create)(
        name="WS Division", division_type=DivisionType.DEPARTMENT
    )
    position = await sync_to_async(Position.objects.create)(
        name="WS Position", level=1
    )
    employee = await sync_to_async(Employee.objects.create)(
        full_name="WS Employee", division=division, position=position, user=user
    )

    communicator = WebsocketCommunicator(application, f"/ws/notifications/")
    # attach authenticated user to scope if authentication middleware expects it
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    await sync_to_async(EmployeeStatusLog.objects.create)(
        employee=employee,
        status=EmployeeStatusType.ON_LEAVE,
        date_from=timezone.now().date(),
    )

    response = await communicator.receive_json_from()
    assert response["message"]["type"] == "status_update"
    assert response["message"]["employee_id"] == employee.id

    await communicator.disconnect()
