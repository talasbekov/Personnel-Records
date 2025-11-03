from abc import ABC, abstractmethod
from organization_management.apps.statuses.models import EmployeeStatus

class StatusRepository(ABC):
    @abstractmethod
    def save(self, status_log: EmployeeStatus):
        pass
