"""
Management команда для автоматической обработки статусов сотрудников

Эта команда должна запускаться каждый день (например, через cron или celery beat)
для автоматического обновления состояний статусов.

Выполняет две основные задачи:
1. Активация запланированных статусов (PLANNED -> ACTIVE)
2. Завершение истекших статусов (ACTIVE -> COMPLETED)

Использование:
    python manage.py process_statuses
    python manage.py process_statuses --date 2025-11-17
    python manage.py process_statuses --verbose
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date

from organization_management.apps.statuses.application.services import StatusApplicationService


class Command(BaseCommand):
    help = 'Автоматическая обработка статусов сотрудников (активация запланированных, завершение истекших)'

    def add_arguments(self, parser):
        """Добавление аргументов командной строки"""
        parser.add_argument(
            '--date',
            type=str,
            help='Дата для обработки в формате YYYY-MM-DD (по умолчанию - сегодня)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод информации',
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        service = StatusApplicationService()

        # Определяем дату обработки
        if options['date']:
            try:
                target_date = date.fromisoformat(options['date'])
                self.stdout.write(f"Обработка статусов на дату: {target_date}")
            except ValueError:
                self.stderr.write(
                    self.style.ERROR(f"Неверный формат даты: {options['date']}. Используйте YYYY-MM-DD")
                )
                return
        else:
            target_date = timezone.now().date()
            self.stdout.write(f"Обработка статусов на текущую дату: {target_date}")

        verbose = options['verbose']

        # 1. Активация запланированных статусов
        self.stdout.write("\n" + "="*60)
        self.stdout.write("1. Активация запланированных статусов (PLANNED -> ACTIVE)")
        self.stdout.write("="*60)

        try:
            applied_statuses = service.apply_planned_statuses(target_date=target_date)

            if applied_statuses:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Активировано статусов: {len(applied_statuses)}")
                )

                if verbose:
                    for status in applied_statuses:
                        self.stdout.write(
                            f"  - ID {status.id}: {status.employee} - "
                            f"{status.get_status_type_display()} ({status.start_date} - {status.end_date or 'н/д'})"
                        )
            else:
                self.stdout.write(
                    self.style.WARNING("  Нет запланированных статусов для активации")
                )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"✗ Ошибка при активации статусов: {str(e)}")
            )

        # 2. Завершение истекших статусов
        self.stdout.write("\n" + "="*60)
        self.stdout.write("2. Завершение истекших статусов (ACTIVE -> COMPLETED)")
        self.stdout.write("="*60)

        try:
            completed_statuses = service.complete_expired_statuses(target_date=target_date)

            if completed_statuses:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Завершено статусов: {len(completed_statuses)}")
                )

                if verbose:
                    for status in completed_statuses:
                        self.stdout.write(
                            f"  - ID {status.id}: {status.employee} - "
                            f"{status.get_status_type_display()} (завершён {status.end_date})"
                        )
            else:
                self.stdout.write(
                    self.style.WARNING("  Нет истекших статусов для завершения")
                )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"✗ Ошибка при завершении статусов: {str(e)}")
            )

        # Итоговая информация
        self.stdout.write("\n" + "="*60)
        total_processed = len(applied_statuses) + len(completed_statuses)
        if total_processed > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ Обработка завершена. Всего обработано статусов: {total_processed}")
            )
        else:
            self.stdout.write("  Нет статусов для обработки")
        self.stdout.write("="*60 + "\n")
