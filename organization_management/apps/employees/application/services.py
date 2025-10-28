from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.employees.domain.repositories import EmployeeRepository
from organization_management.apps.employees.infrastructure.repositories import EmployeeRepositoryImpl
from organization_management.apps.employees.domain.value_objects import FullName

class EmployeeApplicationService:
    def __init__(self, employee_repository: EmployeeRepository = EmployeeRepositoryImpl()):
        self.employee_repository = employee_repository

    def hire_employee(self, user, full_name, position_id, division_id):
        position = Position.objects.get(id=position_id)
        division = Division.objects.get(id=division_id)
        employee = Employee(
            full_name=FullName(first_name=full_name.split(' ')[0], last_name=full_name.split(' ')[1]),
            position=position,
            division=division,
            employee_number=str(Employee.objects.count() + 1),
        )
        self.employee_repository.save(employee)
        return employee

    def transfer_employee(self, user, employee_id, new_division_id, new_position_id):
        employee = self.employee_repository.get_by_id(employee_id)
        new_division = Division.objects.get(id=new_division_id)
        new_position = Position.objects.get(id=new_position_id)
        employee.division = new_division
        employee.position = new_position
        self.employee_repository.save(employee)

    def terminate_employee(self, user, employee_id):
        employee = self.employee_repository.get_by_id(employee_id)
        employee.is_active = False
        self.employee_repository.save(employee)
