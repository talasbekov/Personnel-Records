from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from .models import Position, Division, Employee, EmployeeStatusLog, EmployeeStatusType, DivisionType
import datetime

class CopyStatusesCommandTest(TestCase):
    def setUp(self):
        self.pos = Position.objects.create(name="Commander", level=1)
        self.div = Division.objects.create(name="Command Center", division_type=DivisionType.OFFICE)

        self.today = datetime.date.today()
        self.yesterday = self.today - datetime.timedelta(days=1)

        # Employee 1: Was on leave yesterday, should be copied.
        self.emp1 = Employee.objects.create(full_name="Adam Alpha", position=self.pos, division=self.div)
        EmployeeStatusLog.objects.create(
            employee=self.emp1, status=EmployeeStatusType.ON_LEAVE,
            date_from=self.yesterday, date_to=self.yesterday
        )

        # Employee 2: Is in the default 'In Line-up' status, should be skipped.
        self.emp2 = Employee.objects.create(full_name="Betty Beta", position=self.pos, division=self.div)

        # Employee 3: Has a multi-day status that already covers today, should be skipped.
        self.emp3 = Employee.objects.create(full_name="Charles Charlie", position=self.pos, division=self.div)
        EmployeeStatusLog.objects.create(
            employee=self.emp3, status=EmployeeStatusType.BUSINESS_TRIP,
            date_from=self.yesterday, date_to=self.today
        )

        # Employee 4: Has a manual status set for today, should be skipped.
        self.emp4 = Employee.objects.create(full_name="Diana Delta", position=self.pos, division=self.div)
        EmployeeStatusLog.objects.create( # Status for yesterday
            employee=self.emp4, status=EmployeeStatusType.SICK_LEAVE,
            date_from=self.yesterday, date_to=self.yesterday
        )
        EmployeeStatusLog.objects.create( # Manual status for today
            employee=self.emp4, status=EmployeeStatusType.ON_LEAVE,
            date_from=self.today, date_to=self.today, is_auto_copied=False
        )

    def test_copy_statuses_command(self):
        """
        Tests the copy_statuses management command.
        """
        # --- First run ---
        call_command('copy_statuses')

        # Check Employee 1: A new status should have been created for today.
        new_status_emp1 = EmployeeStatusLog.objects.filter(employee=self.emp1, date_from=self.today).first()
        self.assertIsNotNone(new_status_emp1)
        self.assertEqual(new_status_emp1.status, EmployeeStatusType.ON_LEAVE)
        self.assertTrue(new_status_emp1.is_auto_copied)

        # Check Employee 2: No new status should be created.
        new_status_emp2 = EmployeeStatusLog.objects.filter(employee=self.emp2, date_from=self.today).exists()
        self.assertFalse(new_status_emp2)

        # Check Employee 3: No new status should be created.
        new_status_emp3 = EmployeeStatusLog.objects.filter(employee=self.emp3, date_from=self.today, is_auto_copied=True).exists()
        self.assertFalse(new_status_emp3)

        # Check Employee 4: No new status should be created.
        new_status_emp4 = EmployeeStatusLog.objects.filter(employee=self.emp4, date_from=self.today, is_auto_copied=True).exists()
        self.assertFalse(new_status_emp4)

        # --- Second run (Idempotency Check) ---
        # The command should not create any new duplicates.
        initial_log_count = EmployeeStatusLog.objects.count()
        call_command('copy_statuses')
        final_log_count = EmployeeStatusLog.objects.count()

        self.assertEqual(initial_log_count, final_log_count, "Running the command again should not create duplicate statuses.")
