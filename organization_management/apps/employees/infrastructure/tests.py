from django.test import TestCase
from django.contrib.auth import get_user_model
from organization_management.apps.employees.application.services import EmployeeApplicationService
from organization_management.apps.employees.infrastructure.repositories import EmployeeRepositoryImpl
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.employees.models import Employee
from organization_management.apps.auth.models import UserRole

class EmployeeApplicationServiceIntegrationTest(TestCase):
    def setUp(self):
        self.service = EmployeeApplicationService(EmployeeRepositoryImpl())
        self.user = get_user_model().objects.create_user(username='testuser', role=UserRole.ROLE_4)
        self.division = Division.objects.create(name='Test Division', division_type='DEPARTMENT')
        self.position = Position.objects.create(name='Test Position', level=1)

    def test_hire_employee_integration(self):
        employee = self.service.hire_employee(
            user=self.user,
            full_name='Test Employee',
            position_id=self.position.id,
            division_id=self.division.id,
        )
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(employee.full_name.first_name, 'Test')
