from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.employees.models import Employee
from organization_management.apps.statuses.domain.repositories import StatusRepository
from organization_management.apps.statuses.infrastructure.repositories import StatusRepositoryImpl

class StatusApplicationService:
    def __init__(self, status_repository: StatusRepository = StatusRepositoryImpl()):
        self.status_repository = status_repository

    def create_status(self, user, employee_id, status, date_from, date_to=None, comment=None):
        employee = Employee.objects.get(id=employee_id)
        status_log = EmployeeStatus(
            employee=employee,
            status=status,
            date_from=date_from,
            date_to=date_to,
            comment=comment,
            created_by=user,
        )
        self.status_repository.save(status_log)
        return status_log
