from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.statuses.domain.repositories import StatusRepository

class StatusRepositoryImpl(StatusRepository):
    def save(self, status_log: EmployeeStatus):
        status_log.save()
