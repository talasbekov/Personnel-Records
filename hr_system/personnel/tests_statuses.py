from django.test import TestCase
from django.contrib.auth.models import User
from .models import Position, Division, Employee, EmployeeStatusLog, EmployeeStatusType, UserProfile, UserRole, DivisionType
import datetime

class StatusLogicTest(TestCase):
    def setUp(self):
        # Basic setup required for creating an employee
        self.pos1 = Position.objects.create(name="Tester", level=50)
        self.div1 = Division.objects.create(name="Test Division", division_type=DivisionType.OFFICE)
        self.employee = Employee.objects.create(full_name="Test Employee", position=self.pos1, division=self.div1)

    def test_auto_revert_to_default_status(self):
        """
        Tests that an employee's status automatically reverts to the default 'В строю'
        after a temporary status period has ended.
        """
        # 1. Set a temporary status for a defined period
        start_date = datetime.date(2025, 1, 1)
        end_date = datetime.date(2025, 1, 10)
        EmployeeStatusLog.objects.create(
            employee=self.employee,
            status=EmployeeStatusType.ON_LEAVE,
            date_from=start_date,
            date_to=end_date
        )

        # 2. Check status *during* the leave period
        date_during_leave = datetime.date(2025, 1, 5)
        current_status_during = self.employee.get_current_status(date=date_during_leave)
        self.assertEqual(current_status_during, EmployeeStatusType.ON_LEAVE)

        # 3. Check status on the last day of leave
        last_day_status = self.employee.get_current_status(date=end_date)
        self.assertEqual(last_day_status, EmployeeStatusType.ON_LEAVE)

        # 4. Check status *after* the leave period has expired
        date_after_leave = datetime.date(2025, 1, 11)
        current_status_after = self.employee.get_current_status(date=date_after_leave)
        self.assertEqual(
            current_status_after,
            EmployeeStatusType.ON_DUTY_SCHEDULED, # ON_DUTY_SCHEDULED is 'В строю'
            "Employee status should revert to the default after the status period ends."
        )

    def test_no_status_logs_returns_default(self):
        """
        Tests that if an employee has no status logs, their status is the default.
        """
        status = self.employee.get_current_status()
        self.assertEqual(status, EmployeeStatusType.ON_DUTY_SCHEDULED)
