import pytest
from datetime import date
from organization_management.apps.employees.application.services import EmployeeApplicationService
from organization_management.apps.employees.domain.repositories import EmployeeRepository
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position

@pytest.mark.django_db
class TestEmployeeApplicationService:
    def test_hire_employee_success(self, mocker):
        """Тест успешного приема на работу"""
        mock_repo = mocker.Mock(spec=EmployeeRepository)
        service = EmployeeApplicationService(employee_repository=mock_repo)

        division = Division.objects.create(name="Test Division", division_type="OFFICE")
        position = Position.objects.create(name="Test Position", level=1)

        service.hire_employee(
            user=None,
            full_name='Иван Иванов',
            position_id=position.id,
            division_id=division.id,
        )

        mock_repo.save.assert_called_once()
