from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from .models import Position, Division, Employee, EmployeeStatusLog, EmployeeStatusType, UserProfile, UserRole, DivisionType
import datetime

class StatusLogicTest(APITestCase):
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

    def test_conflicting_status_overlap_is_prevented(self):
        """
        Tests that creating a mutually exclusive status that overlaps with an
        existing one is prevented by the serializer validation.
        """
        # Existing status: On Leave from Jan 10 to Jan 20
        EmployeeStatusLog.objects.create(
            employee=self.employee, status=EmployeeStatusType.ON_LEAVE,
            date_from=datetime.date(2025, 1, 10), date_to=datetime.date(2025, 1, 20)
        )

        # Attempt to create a new status: Business Trip from Jan 15 to Jan 25
        url = '/api/personnel/status-logs/' # Assuming a standard ViewSet URL
        data = {
            "employee_id": self.employee.id,
            "status": EmployeeStatusType.BUSINESS_TRIP,
            "date_from": datetime.date(2025, 1, 15),
            "date_to": datetime.date(2025, 1, 25)
        }

        # We need an authenticated user to create a log
        user = User.objects.create_user(username='testcreator', password='password')
        self.client.force_authenticate(user=user)

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("conflicts with an existing status", response.data['non_field_errors'][0])

    def test_allowed_status_overlap_is_permitted(self):
        """
        Tests that a coexisting status (like SECONDED_OUT) can overlap with
        another status (like ON_LEAVE).
        """
        # Existing status: Seconded Out from Jan 1 to Feb 28
        EmployeeStatusLog.objects.create(
            employee=self.employee, status=EmployeeStatusType.SECONDED_OUT,
            date_from=datetime.date(2025, 1, 1), date_to=datetime.date(2025, 2, 28)
        )

        # Attempt to create a new status: On Leave from Jan 15 to Jan 25
        url = '/api/personnel/status-logs/'
        data = {
            "employee_id": self.employee.id,
            "status": EmployeeStatusType.ON_LEAVE,
            "date_from": datetime.date(2025, 1, 15),
            "date_to": datetime.date(2025, 1, 25)
        }

        user = User.objects.create_user(username='testcreator2', password='password')
        self.client.force_authenticate(user=user)

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
