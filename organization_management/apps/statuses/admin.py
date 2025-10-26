from django.contrib import admin
from organization_management.apps.statuses.models import EmployeeStatusLog, DivisionStatusUpdate

admin.site.register(EmployeeStatusLog)
admin.site.register(DivisionStatusUpdate)
