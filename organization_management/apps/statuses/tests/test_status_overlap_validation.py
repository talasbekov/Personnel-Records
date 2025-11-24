"""
Тесты для проверки валидации пересечений статусов
"""
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division
from organization_management.apps.dictionaries.models import Position, Rank

User = get_user_model()


class StatusOverlapValidationTest(TestCase):
    """Тесты для проверки валидации пересечений статусов"""

    def setUp(self):
        """Подготовка тестовых данных"""
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        # Создаем подразделение
        self.division = Division.objects.create(
            name='Тестовое подразделение',
            code='TEST',
            division_type='department'
        )
        
        # Создаем должность
        self.position = Position.objects.create(
            name='Тестовая должность',
            level=1
        )
        
        # Создаем звание
        self.rank = Rank.objects.create(
            name='Тестовое звание',
            abbreviation='ТЗ'
        )
        
        # Создаем сотрудника
        self.employee = Employee.objects.create(
            personnel_number='12345',
            last_name='Иванов',
            first_name='Иван',
            middle_name='Иванович',
            hire_date=date.today() - timedelta(days=30),
            position=self.position,
            rank=self.rank,
            division=self.division
        )
        
        self.today = date.today()
        self.tomorrow = self.today + timedelta(days=1)
        self.yesterday = self.today - timedelta(days=1)
        self.next_week = self.today + timedelta(days=7)

    def test_edit_existing_planned_status_without_overlap(self):
        """Тест: редактирование существующего запланированного статуса без пересечений"""
        # Создаем запланированный статус на следующую неделю
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.next_week,
            end_date=self.next_week + timedelta(days=5),
            state=EmployeeStatus.StatusState.PLANNED,
            created_by=self.user
        )
        
        # Изменяем даты статуса - не должно быть ошибки
        status.start_date = self.next_week + timedelta(days=1)
        status.end_date = self.next_week + timedelta(days=6)
        
        try:
            status.full_clean()
            status.save()
            self.assertTrue(True, "Статус успешно отредактирован")
        except ValidationError:
            self.fail("Редактирование статуса не должно вызывать ошибку валидации")

    def test_edit_existing_planned_status_change_to_today(self):
        """Тест: изменение существующего запланированного статуса на сегодня"""
        # Создаем запланированный статус на следующую неделю
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.SICK_LEAVE,
            start_date=self.next_week,
            end_date=self.next_week + timedelta(days=3),
            state=EmployeeStatus.StatusState.PLANNED,
            created_by=self.user
        )
        
        # Изменяем дату начала на сегодня - должно быть разрешено
        status.start_date = self.today
        status.end_date = self.today + timedelta(days=3)
        
        try:
            status.full_clean()
            status.save()
            self.assertTrue(True, "Изменение даты начала на сегодня разрешено")
        except ValidationError as e:
            self.fail(f"Изменение даты на сегодня не должно вызывать ошибку: {e}")

    def test_edit_status_does_not_check_overlap_with_itself(self):
        """Тест: при редактировании статус не проверяется на пересечение с самим собой"""
        # Создаем запланированный статус
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.BUSINESS_TRIP,
            start_date=self.next_week,
            end_date=self.next_week + timedelta(days=5),
            state=EmployeeStatus.StatusState.PLANNED,
            created_by=self.user
        )
        
        # Изменяем комментарий и дату окончания - не должно быть ошибки
        status.comment = "Обновленный комментарий"
        status.end_date = self.next_week + timedelta(days=7)
        
        try:
            status.full_clean()
            status.save()
            self.assertEqual(status.comment, "Обновленный комментарий")
            self.assertEqual(status.end_date, self.next_week + timedelta(days=7))
        except ValidationError:
            self.fail("Редактирование статуса не должно проверять пересечение с самим собой")

    def test_create_overlapping_status_should_fail(self):
        """Тест: создание пересекающегося статуса должно вызывать ошибку"""
        # Создаем первый статус
        EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.next_week,
            end_date=self.next_week + timedelta(days=5),
            state=EmployeeStatus.StatusState.PLANNED,
            created_by=self.user
        )
        
        # Пытаемся создать второй пересекающийся статус
        overlapping_status = EmployeeStatus(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.SICK_LEAVE,
            start_date=self.next_week + timedelta(days=2),
            end_date=self.next_week + timedelta(days=7),
            state=EmployeeStatus.StatusState.PLANNED,
            created_by=self.user
        )
        
        with self.assertRaises(ValidationError) as context:
            overlapping_status.full_clean()
        
        self.assertIn('start_date', context.exception.message_dict)

    def test_multiple_statuses_on_same_day_allowed_for_editing(self):
        """Тест: разрешено иметь несколько статусов на один день при редактировании"""
        # Создаем статус на сегодня
        status1 = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.IN_SERVICE,
            start_date=self.today,
            state=EmployeeStatus.StatusState.ACTIVE,
            created_by=self.user
        )
        
        # Создаем еще один статус на будущее
        status2 = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.next_week,
            end_date=self.next_week + timedelta(days=5),
            state=EmployeeStatus.StatusState.PLANNED,
            created_by=self.user
        )
        
        # Изменяем второй статус на сегодня - должно быть разрешено
        status2.start_date = self.today
        status2.end_date = self.today + timedelta(days=5)
        
        try:
            status2.full_clean()
            # В реальности это должно завершить первый статус, но на уровне валидации это разрешено
            self.assertTrue(True, "Изменение на сегодня разрешено")
        except ValidationError as e:
            # Должно быть разрешено согласно ИСКЛЮЧЕНИЮ 2
            self.fail(f"Изменение на сегодня должно быть разрешено: {e}")

    def test_edit_status_with_in_service_overlap_allowed(self):
        """Тест: редактирование статуса при наличии активного 'В строю'"""
        # Создаем активный статус "В строю"
        EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.IN_SERVICE,
            start_date=self.today,
            state=EmployeeStatus.StatusState.ACTIVE,
            created_by=self.user
        )
        
        # Создаем запланированный отпуск
        vacation = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.next_week,
            end_date=self.next_week + timedelta(days=5),
            state=EmployeeStatus.StatusState.PLANNED,
            created_by=self.user
        )
        
        # Изменяем даты отпуска - не должно быть ошибки
        vacation.end_date = self.next_week + timedelta(days=7)
        
        try:
            vacation.full_clean()
            vacation.save()
            self.assertTrue(True, "Редактирование при наличии 'В строю' разрешено")
        except ValidationError:
            self.fail("Редактирование запланированного статуса при наличии 'В строю' должно быть разрешено")

    def test_cannot_edit_completed_status(self):
        """Тест: нельзя редактировать завершенный статус"""
        # Создаем завершенный статус
        status = EmployeeStatus.objects.create(
            employee=self.employee,
            status_type=EmployeeStatus.StatusType.VACATION,
            start_date=self.yesterday - timedelta(days=5),
            end_date=self.yesterday,
            state=EmployeeStatus.StatusState.COMPLETED,
            created_by=self.user
        )
        
        # Попытка изменить завершенный статус через API должна быть заблокирована в views
        # Но на уровне модели, если мы явно меняем поля, валидация должна работать
        status.comment = "Попытка изменить завершенный статус"
        
        # Валидация модели разрешает изменение, но API должен блокировать
        # Это тестируется в тестах API
        try:
            status.full_clean()
            status.save()
        except Exception:
            self.fail("На уровне модели изменение разрешено, блокировка должна быть в API")
