from django.contrib import admin
from organization_management.apps.employees.models import Employee, EmployeeTransferLog

admin.site.register(Employee)
admin.site.register(EmployeeTransferLog)
