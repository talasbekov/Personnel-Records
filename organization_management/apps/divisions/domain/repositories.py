from abc import ABC, abstractmethod
from typing import List
from organization_management.apps.divisions.models import Division

class DivisionRepository(ABC):
    """
    Абстрактный репозиторий для работы с подразделениями.
    Определяет контракт, которому должны следовать конкретные реализации.
    """
    @abstractmethod
    def get_by_id(self, division_id: int) -> Division:
        pass

    @abstractmethod
    def get_all(self) -> List[Division]:
        pass

    @abstractmethod
    def get_tree(self) -> List[Division]:
        pass

    @abstractmethod
    def add(self, division: Division) -> Division:
        pass

    @abstractmethod
    def update(self, division: Division) -> Division:
        pass

    @abstractmethod
    def delete(self, division_id: int):
        pass
