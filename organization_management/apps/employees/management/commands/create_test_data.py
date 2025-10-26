from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.employees.models import Employee


class Command(BaseCommand):
    help = 'Creates test data for the application'

    def handle(self, *args, **options):
        self.stdout.write('Creating test data...')

        user, _ = get_user_model().objects.get_or_create(username='testuser')
        division, _ = Division.objects.get_or_create(
            name='Test Division',
            defaults={'division_type': 'DEPARTMENT'}
        )
        position, _ = Position.objects.get_or_create(
            name='Test Position',
            defaults={'level': 1}
        )

        Employee.objects.get_or_create(
            user=user,
            first_name='Test',
            last_name='User',
            position=position,
            division=division,
        )

        self.stdout.write(self.style.SUCCESS('Test data created successfully.'))
