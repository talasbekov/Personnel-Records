from abc import ABC, abstractmethod
from organization_management.apps.employees.models import Employee

class EmployeeRepository(ABC):
    @abstractmethod
    def get_by_id(self, employee_id: int) -> Employee:
        pass

    @abstractmethod
    def save(self, employee: Employee):
        pass
