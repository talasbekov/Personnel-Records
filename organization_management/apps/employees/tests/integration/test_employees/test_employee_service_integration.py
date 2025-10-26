import pytest
from datetime import date
from organization_management.apps.employees.application.services import EmployeeApplicationService
from organization_management.apps.employees.infrastructure.repositories import EmployeeRepositoryImpl
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position

@pytest.mark.django_db
class TestEmployeeApplicationServiceIntegration:
    def test_hire_employee_integration_success(self):
        """Интеграционный тест успешного приема на работу"""
        repository = EmployeeRepositoryImpl()
        service = EmployeeApplicationService(employee_repository=repository)

        division = Division.objects.create(name="Test Division", division_type="OFFICE")
        position = Position.objects.create(name="Test Position", level=1)

        employee = service.hire_employee(
            user=None,
            full_name='Петр Петров',
            position_id=position.id,
            division_id=division.id,
        )

        assert employee.id is not None
        assert employee.employee_number is not None
        assert employee.division == division
        assert Employee.objects.count() == 1
