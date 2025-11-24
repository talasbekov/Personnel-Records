"""
Тесты для сервисного слоя управления статусами
"""
from datetime import date, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from organization_management.apps.statuses.application.services import StatusApplicationService
from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.employees.models import Employee
from organization_management.apps.dictionaries.models import Rank


class StatusApplicationServiceTest(TestCase):
    """Тесты для StatusApplicationService"""

    def setUp(self):
        """Подготовка тестовых данных"""
        self.service = StatusApplicationService()

        # Создаем тестовый ранг
        self.rank = Rank.objects.create(
            name='Рядовой',
            short_name='Рядовой'
        )

        # Создаем тестового сотрудника
        self.employee = Employee.objects.create(
            personnel_number='001',
            last_name='Иванов',
            first_name='Иван',
            middle_name='Иванович',
            birth_date=date(1990, 1, 1),
            hire_date=date(2020, 1, 1),
            rank=self.rank
        )

        self.today = timezone.now().date()

    def test_create_status(self):
        """Тест создания статуса"""
        status = self.service.create_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=14),
            comment='Ежегодный отпуск'
        )

        self.assertIsNotNone(status.id)
        self.assertEqual(status.employee, self.employee)
        self.assertEqual(status.status_type, EmployeeStatus.StatusType.VACATION)
        self.assertEqual(status.comment, 'Ежегодный отпуск')

        # Проверяем, что создана запись в истории
        self.assertTrue(status.change_history.exists())

    def test_plan_status(self):
        """Тест планирования статуса"""
        future_date = self.today + timedelta(days=30)
        end_date = future_date + timedelta(days=14)

        status = self.service.plan_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=future_date,
            end_date=end_date,
            comment='Запланированный отпуск'
        )

        self.assertEqual(status.state, EmployeeStatus.StatusState.PLANNED)
        self.assertTrue(status.is_planned)

    def test_extend_status(self):
        """Тест продления статуса"""
        # Создаем активный статус
        status = self.service.create_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.SICK_LEAVE,
            start_date=self.today,
            end_date=self.today + timedelta(days=7)
        )

        # Продлеваем
        new_end = self.today + timedelta(days=14)
        updated_status = self.service.extend_status(
            status_id=status.id,
            new_end_date=new_end
        )

        self.assertEqual(updated_status.end_date, new_end)

        # Проверяем, что создана запись в истории
        history_records = updated_status.change_history.filter(
            change_type=EmployeeStatus.change_history.model.ChangeType.EXTENDED
        )
        self.assertTrue(history_records.exists())

    def test_terminate_status_early(self):
        """Тест досрочного завершения статуса"""
        # Создаем активный статус
        status = self.service.create_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today - timedelta(days=3),
            end_date=self.today + timedelta(days=11)
        )

        # Завершаем досрочно
        termination_date = self.today
        reason = "Производственная необходимость"

        updated_status = self.service.terminate_status_early(
            status_id=status.id,
            termination_date=termination_date,
            reason=reason
        )

        self.assertEqual(updated_status.actual_end_date, termination_date)
        self.assertEqual(updated_status.early_termination_reason, reason)
        self.assertEqual(updated_status.state, EmployeeStatus.StatusState.COMPLETED)

        # Проверяем, что автоматически создан статус "В строю"
        in_service_status = EmployeeStatus.objects.filter(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.IN_SERVICE,
            start_date=termination_date + timedelta(days=1)
        ).first()
        self.assertIsNotNone(in_service_status)

    def test_cancel_status(self):
        """Тест отмены запланированного статуса"""
        # Создаем запланированный статус
        future_date = self.today + timedelta(days=30)
        status = self.service.plan_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=future_date,
            end_date=future_date + timedelta(days=14)
        )

        # Отменяем
        reason = "Изменение планов"
        updated_status = self.service.cancel_status(
            status_id=status.id,
            reason=reason
        )

        self.assertEqual(updated_status.state, EmployeeStatus.StatusState.CANCELLED)

    def test_get_employee_current_status(self):
        """Тест получения текущего статуса сотрудника"""
        # Создаем текущий активный статус
        status = self.service.create_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today - timedelta(days=2),
            end_date=self.today + timedelta(days=5)
        )

        current_status = self.service.get_employee_current_status(self.employee.id)

        self.assertIsNotNone(current_status)
        self.assertEqual(current_status.id, status.id)

    def test_get_employee_status_history(self):
        """Тест получения истории статусов сотрудника"""
        # Создаем несколько статусов
        self.service.create_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today - timedelta(days=60),
            end_date=self.today - timedelta(days=46)
        )

        self.service.create_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.SICK_LEAVE,
            start_date=self.today - timedelta(days=30),
            end_date=self.today - timedelta(days=23)
        )

        history = self.service.get_employee_status_history(self.employee.id)

        self.assertEqual(history.count(), 2)

    def test_get_planned_statuses(self):
        """Тест получения запланированных статусов"""
        # Создаем запланированный статус
        future_date = self.today + timedelta(days=30)
        self.service.plan_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=future_date,
            end_date=future_date + timedelta(days=14)
        )

        planned = self.service.get_planned_statuses(employee_id=self.employee.id)

        self.assertEqual(planned.count(), 1)
        self.assertEqual(planned.first().state, EmployeeStatus.StatusState.PLANNED)

    def test_apply_planned_statuses(self):
        """Тест применения запланированных статусов"""
        # Создаем запланированный статус с датой начала сегодня
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today,
            end_date=self.today + timedelta(days=14),
            state=EmployeeStatus.StatusState.PLANNED
        )

        # Применяем запланированные статусы
        applied = self.service.apply_planned_statuses()

        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0].id, status.id)

        # Проверяем, что статус стал активным
        status.refresh_from_db()
        self.assertEqual(status.state, EmployeeStatus.StatusState.ACTIVE)
        self.assertTrue(status.auto_applied)

    def test_complete_expired_statuses(self):
        """Тест завершения истекших статусов"""
        # Создаем истекший статус
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today - timedelta(days=14),
            end_date=self.today - timedelta(days=1),
            state=EmployeeStatus.StatusState.ACTIVE
        )

        # Завершаем истекшие статусы
        completed = self.service.complete_expired_statuses()

        self.assertEqual(len(completed), 1)

        # Проверяем, что статус завершен
        status.refresh_from_db()
        self.assertEqual(status.state, EmployeeStatus.StatusState.COMPLETED)

        # Проверяем, что создан статус "В строю"
        in_service_status = EmployeeStatus.objects.filter(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.IN_SERVICE
        ).first()
        self.assertIsNotNone(in_service_status)

    def test_validation_error_on_overlapping(self):
        """Тест ошибки валидации при пересечении статусов"""
        # Создаем первый статус
        self.service.create_status(
            employee_id=self.employee.id,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=14)
        )

        # Пытаемся создать пересекающийся статус
        with self.assertRaises(ValidationError):
            self.service.create_status(
                employee_id=self.employee.id,
                status_type=EmployeeStatus.StatusType.SICK_LEAVE,
                start_date=self.today + timedelta(days=7),
                end_date=self.today + timedelta(days=21)
            )
