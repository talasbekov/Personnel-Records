"""
Тесты для моделей статусов
"""
from datetime import date, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from organization_management.apps.statuses.models import (
    EmployeeStatus,
    StatusChangeHistory,
    StatusDocument
)
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Rank


class EmployeeStatusModelTest(TestCase):
    """Тесты модели EmployeeStatus"""

    def setUp(self):
        """Подготовка тестовых данных"""
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

    def test_create_basic_status(self):
        """Тест создания базового статуса"""
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.IN_SERVICE,
            start_date=self.today
        )

        self.assertEqual(status.employee, self.employee)
        self.assertEqual(status.status_type, EmployeeStatus.StatusType.IN_SERVICE)
        self.assertEqual(status.state, EmployeeStatus.StatusState.ACTIVE)

    def test_create_vacation_status(self):
        """Тест создания статуса отпуска"""
        start = self.today + timedelta(days=1)
        end = start + timedelta(days=14)

        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=start,
            end_date=end,
            comment='Ежегодный отпуск'
        )

        self.assertEqual(status.status_type, EmployeeStatus.StatusType.VACATION)
        self.assertEqual(status.start_date, start)
        self.assertEqual(status.end_date, end)
        self.assertEqual(status.state, EmployeeStatus.StatusState.PLANNED)

    def test_validation_end_before_start(self):
        """Тест валидации: дата окончания раньше даты начала"""
        with self.assertRaises(ValidationError):
            status = EmployeeStatus(
                employee=self.employee,
                status_type=EmployeeStatus.StatusType.VACATION,
                start_date=self.today + timedelta(days=10),
                end_date=self.today
            )
            status.full_clean()

    def test_validation_start_before_hire(self):
        """Тест валидации: дата начала раньше даты приема"""
        with self.assertRaises(ValidationError):
            status = EmployeeStatus(
                employee=self.employee,
                status_type=EmployeeStatus.StatusType.VACATION,
                start_date=date(2019, 1, 1),
                end_date=date(2019, 1, 15)
            )
            status.full_clean()

    def test_validation_overlapping_statuses(self):
        """Тест валидации: пересекающиеся статусы"""
        # Создаем первый статус
        EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=14)
        )

        # Пытаемся создать пересекающийся статус
        with self.assertRaises(ValidationError):
            status2 = EmployeeStatus(
                employee=self.employee,
                status_type=EmployeeStatus.StatusType.SICK_LEAVE,
                start_date=self.today + timedelta(days=7),
                end_date=self.today + timedelta(days=21)
            )
            status2.full_clean()

    def test_extend_status(self):
        """Тест продления статуса"""
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.SICK_LEAVE,
            start_date=self.today,
            end_date=self.today + timedelta(days=7)
        )

        new_end = self.today + timedelta(days=14)
        status.extend(new_end)

        status.refresh_from_db()
        self.assertEqual(status.end_date, new_end)

    def test_terminate_early(self):
        """Тест досрочного завершения статуса"""
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today - timedelta(days=3),
            end_date=self.today + timedelta(days=11)
        )

        termination_date = self.today
        reason = "Производственная необходимость"
        status.terminate_early(termination_date, reason)

        status.refresh_from_db()
        self.assertEqual(status.actual_end_date, termination_date)
        self.assertEqual(status.early_termination_reason, reason)
        self.assertEqual(status.state, EmployeeStatus.StatusState.COMPLETED)

    def test_cancel_planned_status(self):
        """Тест отмены запланированного статуса"""
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today + timedelta(days=30),
            end_date=self.today + timedelta(days=44)
        )

        reason = "Изменение планов"
        status.cancel(reason)

        status.refresh_from_db()
        self.assertEqual(status.state, EmployeeStatus.StatusState.CANCELLED)

    def test_is_active_property(self):
        """Тест свойства is_active"""
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today - timedelta(days=2),
            end_date=self.today + timedelta(days=5)
        )

        self.assertTrue(status.is_active)

    def test_is_planned_property(self):
        """Тест свойства is_planned"""
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today + timedelta(days=10),
            end_date=self.today + timedelta(days=24)
        )

        self.assertTrue(status.is_planned)

    def test_effective_end_date_property(self):
        """Тест свойства effective_end_date"""
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.today,
            end_date=self.today + timedelta(days=14)
        )

        # Без досрочного завершения
        self.assertEqual(status.effective_end_date, status.end_date)

        # С досрочным завершением
        early_date = self.today + timedelta(days=7)
        status.actual_end_date = early_date
        status.save()
        self.assertEqual(status.effective_end_date, early_date)


class StatusChangeHistoryModelTest(TestCase):
    """Тесты модели StatusChangeHistory"""

    def setUp(self):
        """Подготовка тестовых данных"""
        self.rank = Rank.objects.create(
            name='Рядовой',
            short_name='Рядовой'
        )

        self.employee = Employee.objects.create(
            personnel_number='001',
            last_name='Иванов',
            first_name='Иван',
            hire_date=date(2020, 1, 1),
            rank=self.rank
        )

        self.status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14)
        )

    def test_create_history_record(self):
        """Тест создания записи истории"""
        history = StatusChangeHistory.objects.create(
            status=self.status,
            change_type=StatusChangeHistory.ChangeType.CREATED,
            comment='Создан статус отпуска'
        )

        self.assertEqual(history.status, self.status)
        self.assertEqual(history.change_type, StatusChangeHistory.ChangeType.CREATED)
        self.assertIsNotNone(history.changed_at)


class StatusDocumentModelTest(TestCase):
    """Тесты модели StatusDocument"""

    def setUp(self):
        """Подготовка тестовых данных"""
        self.rank = Rank.objects.create(
            name='Рядовой',
            short_name='Рядовой'
        )

        self.employee = Employee.objects.create(
            personnel_number='001',
            last_name='Иванов',
            first_name='Иван',
            hire_date=date(2020, 1, 1),
            rank=self.rank
        )

        self.status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.SICK_LEAVE,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=7)
        )

    def test_create_document(self):
        """Тест создания документа"""
        document = StatusDocument.objects.create(
            status=self.status,
            title='Больничный лист',
            description='Лист нетрудоспособности'
        )

        self.assertEqual(document.status, self.status)
        self.assertEqual(document.title, 'Больничный лист')
        self.assertIsNotNone(document.uploaded_at)
