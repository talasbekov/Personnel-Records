import pytest
from organization_management.apps.employees.application.services import EmployeeApplicationService
from organization_management.apps.employees.models import Employee
from organization_management.apps.auth.models import User
from tests.fixtures.factories import DivisionFactory, PositionFactory

@pytest.mark.django_db
class TestEmployeeApplicationService:
    def test_hire_employee(self):
        """
        Тест успешного приема на работу.
        """
        service = EmployeeApplicationService()
        division = DivisionFactory()
        position = PositionFactory()

        validated_data = {
            'personnel_number': '12345',
            'last_name': 'Иванов',
            'first_name': 'Иван',
            'birth_date': '1990-01-01',
            'gender': 'M',
            'division': division,
            'position': position,
            'hire_date': '2024-01-01',
        }

        employee = service.hire_employee(validated_data)

        assert isinstance(employee, Employee)
        assert employee.personnel_number == '12345'
        assert Employee.objects.count() == 1

    def test_hire_employee_with_user_creation(self):
        """
        Тест успешного приема на работу с созданием пользователя.
        """
        service = EmployeeApplicationService()
        division = DivisionFactory()
        position = PositionFactory()

        validated_data = {
            'personnel_number': '12345',
            'last_name': 'Иванов',
            'first_name': 'Иван',
            'birth_date': '1990-01-01',
            'gender': 'M',
            'division': division,
            'position': position,
            'hire_date': '2024-01-01',
            'create_user': True,
            'password': 'password123',
            'work_email': 'ivanov@example.com',
        }

        employee = service.hire_employee(validated_data)

        assert isinstance(employee, Employee)
        assert employee.user is not None
        assert User.objects.count() == 1
        assert employee.user.username == f"user_{employee.personnel_number}"
