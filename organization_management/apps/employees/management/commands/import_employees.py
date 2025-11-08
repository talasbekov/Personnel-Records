import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from organization_management.apps.employees.models import Employee


class Command(BaseCommand):
    help = "Импорт сотрудников из CSV (FULL_NAME → ФИО, IIN → с дополнением до 12 цифр)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Путь к CSV файлу")

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])

        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f"Файл не найден: {csv_path}"))
            return

        created_count = 0
        updated_count = 0

        with open(csv_path, encoding="utf-8-sig") as f:  # <— utf-8-sig убирает BOM
            reader = csv.DictReader(f, delimiter=";", quotechar='"')

            for row in reader:
                full_name = (row.get("FULL_NAME") or "").strip().strip('"')
                iin = (row.get("IIN") or "").strip().strip('"')

                if not full_name:
                    continue

                # Добавляем нули спереди, если меньше 12 символов
                if iin and len(iin) < 12:
                    iin = iin.zfill(12)

                # Разбиваем ФИО
                parts = full_name.split()
                last_name = parts[0] if len(parts) > 0 else ""
                first_name = parts[1] if len(parts) > 1 else ""
                middle_name = " ".join(parts[2:]) if len(parts) > 2 else ""

                # Генерация уникального personnel_number
                base_number = 1000
                while True:
                    personnel_number = str(base_number).zfill(6)
                    if not Employee.objects.filter(personnel_number=personnel_number).exists():
                        break
                    base_number += 1

                # Создаём или обновляем запись
                obj, created = Employee.objects.update_or_create(
                    iin=iin or None,
                    defaults={
                        "personnel_number": personnel_number,
                        "last_name": last_name,
                        "first_name": first_name,
                        "middle_name": middle_name,
                        "is_active": True,
                    },
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Импорт завершён: создано {created_count}, обновлено {updated_count}"
            )
        )
