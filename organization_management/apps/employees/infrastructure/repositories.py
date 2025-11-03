from organization_management.apps.employees.models import Employee
from organization_management.apps.employees.domain.repositories import EmployeeRepository

class EmployeeRepositoryImpl(EmployeeRepository):
    def get_by_id(self, employee_id: int) -> Employee:
        return Employee.objects.get(id=employee_id)

    def save(self, employee: Employee):
        employee.save()
