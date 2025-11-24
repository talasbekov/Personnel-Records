#!/usr/bin/env python
"""
Скрипт для автоматического присвоения статуса "В строю" всем сотрудникам без статуса.

Использование:
    cd Personnel-Records
    python Scripts/assign_default_status.py
"""

import os
import sys
import django
from datetime import date

# Настройка Django окружения
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organization_management.config.settings.production')
django.setup()

from django.contrib.auth.models import User
from organization_management.apps.employees.models import Employee
from organization_management.apps.statuses.models import EmployeeStatus
from django.db import transaction


def assign_default_status():
    """
    Присваивает статус "В строю" всем сотрудникам, у которых нет ни одного статуса.
    """
    print("=" * 80)
    print("Скрипт присвоения статуса 'В строю' сотрудникам без статуса")
    print("=" * 80)
    print()

    # Получаем всех активных сотрудников
    all_employees = Employee.objects.filter(
        employment_status=Employee.EmploymentStatus.WORKING
    ).select_related('staff_unit')

    print(f"Найдено активных сотрудников: {all_employees.count()}")
    print()

    # Находим сотрудников без статуса
    employees_without_status = []

    for employee in all_employees:
        # Проверяем, есть ли хотя бы один статус
        has_status = EmployeeStatus.objects.filter(employee=employee).exists()
        if not has_status:
            employees_without_status.append(employee)

    print(f"Сотрудников без статуса: {len(employees_without_status)}")
    print()

    if not employees_without_status:
        print("✓ Все сотрудники уже имеют статусы!")
        print()
        return

    # Получаем системного пользователя для created_by
    try:
        system_user = User.objects.filter(is_superuser=True).first()
        if not system_user:
            # Если нет суперпользователя, создаем системного пользователя
            system_user = User.objects.create_user(
                username='system',
                email='system@example.com',
                is_staff=True,
                is_superuser=False
            )
            print(f"✓ Создан системный пользователь: {system_user.username}")
    except Exception as e:
        print(f"✗ Ошибка при получении системного пользователя: {e}")
        return

    # Выводим список сотрудников
    print("Сотрудники, которым будет присвоен статус 'В строю':")
    print("-" * 80)
    for i, employee in enumerate(employees_without_status, 1):
        # Получаем подразделение через staff_unit
        if hasattr(employee, 'staff_unit') and employee.staff_unit and employee.staff_unit.division:
            division_name = employee.staff_unit.division.name
        else:
            division_name = "Без подразделения"

        # Получаем должность через staff_unit
        if hasattr(employee, 'staff_unit') and employee.staff_unit and employee.staff_unit.position:
            position_name = employee.staff_unit.position.name
        else:
            position_name = "Без должности"

        print(f"{i}. {employee.last_name} {employee.first_name} - {division_name}, {position_name}")
    print("-" * 80)
    print()

    # Запрашиваем подтверждение
    confirmation = input("Продолжить присвоение статусов? (yes/no): ").strip().lower()

    if confirmation not in ['yes', 'y', 'да', 'д']:
        print("Операция отменена пользователем.")
        return

    print()
    print("Начинаю присвоение статусов...")
    print()

    # Присваиваем статусы в транзакции
    created_count = 0
    errors = []

    with transaction.atomic():
        for employee in employees_without_status:
            try:
                # Создаем статус "В строю"
                status = EmployeeStatus.objects.create(
                    employee=employee,
                    status_type=EmployeeStatus.StatusType.IN_SERVICE,
                    start_date=date.today(),
                    end_date=None,
                    state=EmployeeStatus.StatusState.ACTIVE,
                    comment='Автоматически создан скриптом для сотрудников без статуса',
                    created_by=system_user,
                    actual_end_date=None,
                    early_termination_reason=''
                )
                created_count += 1
                print(f"✓ Создан статус для: {employee.last_name} {employee.first_name} (ID: {employee.id})")
            except Exception as e:
                error_msg = f"✗ Ошибка для {employee.last_name} {employee.first_name} (ID: {employee.id}): {e}"
                errors.append(error_msg)
                print(error_msg)

    print()
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 80)
    print(f"Успешно создано статусов: {created_count}")
    print(f"Ошибок: {len(errors)}")

    if errors:
        print()
        print("Список ошибок:")
        for error in errors:
            print(error)

    print()
    print("✓ Скрипт завершен!")
    print("=" * 80)


if __name__ == '__main__':
    try:
        assign_default_status()
    except KeyboardInterrupt:
        print()
        print("Операция прервана пользователем.")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
