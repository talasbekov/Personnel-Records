from abc import ABC, abstractmethod
from organization_management.apps.statuses.models import EmployeeStatusLog

class StatusRepository(ABC):
    @abstractmethod
    def save(self, status_log: EmployeeStatusLog):
        pass
