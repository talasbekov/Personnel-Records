from typing import List
from organization_management.apps.divisions.models import Division
from organization_management.apps.divisions.domain.repositories import DivisionRepository

class DivisionRepositoryImpl(DivisionRepository):
    """
    Конкретная реализация репозитория для подразделений,
    использующая Django ORM.
    """
    def get_by_id(self, division_id: int) -> Division:
        return Division.objects.get(pk=division_id)

    def get_all(self) -> List[Division]:
        return list(Division.objects.all())

    def get_tree(self) -> List[Division]:
        return list(Division.objects.filter(level=0))

    def add(self, division: Division) -> Division:
        division.save()
        return division

    def update(self, division: Division) -> Division:
        division.save()
        return division

    def delete(self, division_id: int):
        Division.objects.filter(pk=division_id).delete()
