"""
Django management command для автоматического обновления дат статуса "В строю"
Запускать ежедневно через cron
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from organization_management.apps.statuses.models import EmployeeStatus


class Command(BaseCommand):
    help = 'Обновляет дату начала статуса "В строю" для всех активных сотрудников'

    def handle(self, *args, **options):
        today = timezone.now().date()

        # Обновляем все активные статусы "В строю" одним запросом
        # Используем update() для обхода валидации в save()
        updated_count = EmployeeStatus.objects.filter(
            status_type=EmployeeStatus.StatusType.IN_SERVICE,
            state=EmployeeStatus.StatusState.ACTIVE
        ).exclude(
            start_date=today  # Исключаем те, у которых дата уже сегодняшняя
        ).update(
            start_date=today
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно обновлено {updated_count} статусов "В строю" на дату {today}'
            )
        )
