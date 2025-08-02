from django.test import TestCase
from django.contrib.auth.models import User
from personnel.models import SecondmentRequest, EmployeeStatusLog, Vacancy, Employee, Division, Position, DivisionType, EmployeeStatusType
from notifications.models import Notification
from django.utils import timezone

class NotificationSignalTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.create_user(username='testuser1', password='password', is_superuser=True)
        cls.user2 = User.objects.create_user(username='testuser2', password='password')
        cls.division = Division.objects.create(name='Test Division', division_type=DivisionType.DEPARTMENT)
        cls.position = Position.objects.create(name='Test Position', level=1)
        # This will create one notification
        cls.employee = Employee.objects.create(full_name='Test Employee', division=cls.division, position=cls.position, user=cls.user2)

    def test_secondment_notification_created(self):
        """
        Test that a notification is created when a SecondmentRequest is created.
        """
        SecondmentRequest.objects.create(
            employee=self.employee,
            from_division=self.division,
            to_division=self.division,
            requested_by=self.user1,
            date_from=timezone.now().date(),
            reason='Test'
        )
        self.assertEqual(Notification.objects.count(), 2)

    def test_status_update_notification_created(self):
        """
        Test that a notification is created when an EmployeeStatusLog is created.
        """
        EmployeeStatusLog.objects.create(
            employee=self.employee,
            status=EmployeeStatusType.ON_LEAVE,
            date_from=timezone.now().date()
        )
        self.assertEqual(Notification.objects.count(), 2)

    def test_vacancy_notification_created(self):
        """
        Test that a notification is created when a Vacancy is created.
        """
        staffing_unit = self.division.staffing_units.create(position=self.position, quantity=1)
        Vacancy.objects.create(
            staffing_unit=staffing_unit,
            title='New Test Vacancy',
            created_by=self.user1
        )
        self.assertEqual(Notification.objects.count(), 2)

    def test_employee_update_notification_created(self):
        """
        Test that a notification is created when an Employee is updated.
        """
        self.employee.full_name = 'Updated Name'
        self.employee.save()
        # Should be 2 notifications: 1 from create, 1 from update
        self.assertEqual(Notification.objects.count(), 2)

    def test_employee_delete_notification_created(self):
        """
        Test that a notification is created when an Employee is deleted.
        """
        self.employee.delete()
        # 1 from create, 1 from delete
        self.assertEqual(Notification.objects.count(), 2)
