from django.contrib import admin
from organization_management.apps.dictionaries import models

admin.site.register(models.Position)
admin.site.register(models.StatusType)
admin.site.register(models.DismissalReason)
admin.site.register(models.TransferReason)
admin.site.register(models.VacancyReason)
admin.site.register(models.EducationType)
admin.site.register(models.DocumentType)
admin.site.register(models.SystemSetting)
