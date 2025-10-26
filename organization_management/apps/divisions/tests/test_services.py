import pytest
from unittest.mock import Mock
from organization_management.apps.divisions.application.services import DivisionApplicationService
from organization_management.apps.divisions.domain.repositories import DivisionRepository
from organization_management.apps.divisions.models import Division

@pytest.mark.django_db
class TestDivisionApplicationService:
    def test_create_division(self):
        """Тест создания подразделения через сервис"""
        mock_repo = Mock(spec=DivisionRepository)
        service = DivisionApplicationService(division_repository=mock_repo)

        service.create_division(
            name='Test Division',
            code='TD01',
            division_type='division'
        )

        mock_repo.add.assert_called_once()
