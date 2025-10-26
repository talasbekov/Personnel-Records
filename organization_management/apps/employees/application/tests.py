from django.test import TestCase
from django.contrib.auth import get_user_model
from organization_management.apps.employees.application.services import EmployeeApplicationService
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.employees.models import Employee
from organization_management.apps.auth.models import UserRole

class EmployeeApplicationServiceTest(TestCase):
    def setUp(self):
        self.service = EmployeeApplicationService()
        self.user = get_user_model().objects.create_user(username='testuser', role=UserRole.ROLE_4)
        self.division = Division.objects.create(name='Test Division', division_type='DEPARTMENT')
        self.position = Position.objects.create(name='Test Position', level=1)
        self.employee = Employee.objects.create(
            first_name='Test',
            last_name='User',
            position=self.position,
            division=self.division,
        )

    def test_hire_employee(self):
        employee = self.service.hire_employee(
            user=self.user,
            full_name='Test Employee',
            position_id=self.position.id,
            division_id=self.division.id,
        )
        self.assertEqual(employee.full_name.first_name, 'Test')
        self.assertEqual(employee.full_name.last_name, 'Employee')
        self.assertEqual(employee.position, self.position)
        self.assertEqual(employee.division, self.division)

    def test_transfer_employee(self):
        new_division = Division.objects.create(name='New Division', division_type='DEPARTMENT')
        new_position = Position.objects.create(name='New Position', level=2)

        self.service.transfer_employee(
            user=self.user,
            employee_id=self.employee.id,
            new_division_id=new_division.id,
            new_position_id=new_position.id,
        )

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.division, new_division)
        self.assertEqual(self.employee.position, new_position)

    def test_terminate_employee(self):
        self.service.terminate_employee(
            user=self.user,
            employee_id=self.employee.id,
        )

        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
