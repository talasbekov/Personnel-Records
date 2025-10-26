from django.core.management.base import BaseCommand
from organization_management.apps.dictionaries.models import (
    Position,
    StatusType,
    DismissalReason,
    TransferReason,
    VacancyReason,
    EducationType,
    DocumentType,
    SystemSetting,
)

class Command(BaseCommand):
    help = 'Initializes the dictionaries with some default data'

    def handle(self, *args, **options):
        self.stdout.write('Initializing dictionaries...')

        Position.objects.get_or_create(name='Director', defaults={'level': 1})
        Position.objects.get_or_create(name='Manager', defaults={'level': 2})
        Position.objects.get_or_create(name='Developer', defaults={'level': 3})

        StatusType.objects.get_or_create(name='In Service')
        StatusType.objects.get_or_create(name='Vacation')
        StatusType.objects.get_or_create(name='Sick Leave')

        DismissalReason.objects.get_or_create(name='Resignation')
        DismissalReason.objects.get_or_create(name='Termination')

        TransferReason.objects.get_or_create(name='Promotion')
        TransferReason.objects.get_or_create(name='Reorganization')

        VacancyReason.objects.get_or_create(name='New Position')
        VacancyReason.objects.get_or_create(name='Replacement')

        EducationType.objects.get_or_create(name='Higher Education')
        EducationType.objects.get_or_create(name='Secondary Education')

        DocumentType.objects.get_or_create(name='Passport')
        DocumentType.objects.get_or_create(name='Diploma')

        SystemSetting.objects.get_or_create(key='default_language', defaults={'value': 'en-us'})

        self.stdout.write(self.style.SUCCESS('Dictionaries initialized successfully.'))
