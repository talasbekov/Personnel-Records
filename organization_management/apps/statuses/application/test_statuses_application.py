from django.test import TestCase
from django.contrib.auth import get_user_model
from organization_management.apps.statuses.application.services import StatusApplicationService
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.statuses.models import EmployeeStatusType
from organization_management.apps.auth.models import User
UserRole = User.RoleType

class StatusApplicationServiceTest(TestCase):
    def setUp(self):
        self.service = StatusApplicationService()
        self.user = get_user_model().objects.create_user(username='testuser', role=UserRole.ROLE_4)
        self.division = Division.objects.create(name='Test Division', division_type='DEPARTMENT')
        self.position = Position.objects.create(name='Test Position', level=1)
        self.employee = Employee.objects.create(
            first_name='Test',
            last_name='User',
            position=self.position,
            division=self.division,
        )

    def test_create_status(self):
        status_log = self.service.create_status(
            user=self.user,
            employee_id=self.employee.id,
            status=EmployeeStatusType.ON_LEAVE,
            date_from='2025-01-01',
        )
        self.assertEqual(status_log.employee, self.employee)
        self.assertEqual(status_log.status, EmployeeStatusType.ON_LEAVE)
