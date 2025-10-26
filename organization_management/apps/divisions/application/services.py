from typing import List
from organization_management.apps.divisions.models import Division
from organization_management.apps.divisions.domain.repositories import DivisionRepository
from organization_management.apps.divisions.infrastructure.repositories import DivisionRepositoryImpl

class DivisionApplicationService:
    """
    Сервис для управления бизнес-логикой подразделений.
    """
    def __init__(self, division_repository: DivisionRepository = DivisionRepositoryImpl()):
        self.division_repository = division_repository

    def get_division_by_id(self, division_id: int) -> Division:
        return self.division_repository.get_by_id(division_id)

    def get_all_divisions(self) -> List[Division]:
        return self.division_repository.get_all()

    def get_division_tree(self) -> List[Division]:
        return self.division_repository.get_tree()

    def create_division(self, name: str, code: str, division_type: str, parent_id: int = None) -> Division:
        parent = self.division_repository.get_by_id(parent_id) if parent_id else None
        division = Division(name=name, code=code, division_type=division_type, parent=parent)
        return self.division_repository.add(division)

    def update_division(self, division_id: int, name: str, code: str, division_type: str, parent_id: int = None) -> Division:
        division = self.division_repository.get_by_id(division_id)
        parent = self.division_repository.get_by_id(parent_id) if parent_id else None
        division.name = name
        division.code = code
        division.division_type = division_type
        division.parent = parent
        return self.division_repository.update(division)

    def delete_division(self, division_id: int):
        self.division_repository.delete(division_id)
