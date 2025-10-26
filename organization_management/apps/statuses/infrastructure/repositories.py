from organization_management.apps.statuses.models import EmployeeStatusLog
from organization_management.apps.statuses.domain.repositories import StatusRepository

class StatusRepositoryImpl(StatusRepository):
    def save(self, status_log: EmployeeStatusLog):
        status_log.save()
