import pytest
from organization_management.apps.divisions.infrastructure.repositories import DivisionRepositoryImpl
from organization_management.apps.divisions.models import Division

@pytest.mark.django_db
class TestDivisionRepositoryImpl:
    def test_add_and_get_division(self):
        """Интеграционный тест добавления и получения подразделения"""
        repo = DivisionRepositoryImpl()
        division = Division(
            name='Test Division',
            code='TD01',
            division_type='division'
        )
        repo.add(division)

        retrieved_division = repo.get_by_id(division.id)
        assert retrieved_division is not None
        assert retrieved_division.name == 'Test Division'
