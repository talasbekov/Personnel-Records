"""
Django management command для обновления фотографий сотрудников по ИИН
Использование: python manage.py update_employee_photos
"""
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from organization_management.apps.employees.models import Employee


class Command(BaseCommand):
    help = 'Обновляет ссылки на фотографии сотрудников в БД на основе файлов {iin}.jpg'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать изменения без сохранения в БД',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Путь к папке с фотографиями
        photos_dir = Path(settings.MEDIA_ROOT) / 'employees' / 'photos'

        if not photos_dir.exists():
            self.stdout.write(
                self.style.ERROR(f'Папка {photos_dir} не существует!')
            )
            return

        self.stdout.write(f'Поиск фотографий в: {photos_dir}')
        self.stdout.write('')

        # Счетчики
        found_count = 0
        updated_count = 0
        not_found_count = 0
        skipped_count = 0

        # Получаем список всех jpg файлов
        photo_files = list(photos_dir.glob('*.jpg'))
        self.stdout.write(f'Найдено файлов: {len(photo_files)}')
        self.stdout.write('')

        for photo_file in photo_files:
            # Извлекаем ИИН из имени файла (без расширения)
            iin = photo_file.stem

            # Пропускаем файлы с некорректными именами
            if not iin.isdigit() or len(iin) != 12:
                self.stdout.write(
                    self.style.WARNING(f'  Пропущен файл {photo_file.name} (некорректное имя)')
                )
                skipped_count += 1
                continue

            # Ищем сотрудника по ИИН
            try:
                employee = Employee.objects.get(iin=iin)
                found_count += 1

                # Относительный путь от MEDIA_ROOT
                photo_path = f'employees/photos/{photo_file.name}'

                # Проверяем, нужно ли обновлять
                if employee.photo and employee.photo.name == photo_path:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {iin} - {employee.last_name} {employee.first_name} (уже установлено)')
                    )
                    continue

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(f'  {iin} - {employee.last_name} {employee.first_name} (будет обновлено)')
                    )
                else:
                    # Обновляем поле photo
                    employee.photo = photo_path
                    employee.save(update_fields=['photo', 'updated_at'])
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {iin} - {employee.last_name} {employee.first_name} (обновлено)')
                    )

            except Employee.DoesNotExist:
                not_found_count += 1
                self.stdout.write(
                    self.style.WARNING(f'⚠ {iin} - сотрудник не найден в БД')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ {iin} - ошибка: {str(e)}')
                )

        # Итоги
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('Итоги:'))
        self.stdout.write(f'  Всего файлов: {len(photo_files)}')
        self.stdout.write(f'  Найдено сотрудников: {found_count}')
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'  Обновлено записей: {updated_count}'))
        else:
            self.stdout.write(self.style.WARNING(f'  Будет обновлено: {updated_count} (dry-run режим)'))

        if not_found_count > 0:
            self.stdout.write(self.style.WARNING(f'  Не найдено в БД: {not_found_count}'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'  Пропущено (некорректное имя): {skipped_count}'))

        self.stdout.write('=' * 60)

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Это был пробный запуск (--dry-run).'))
            self.stdout.write('Для реального обновления запустите команду без флага --dry-run')
