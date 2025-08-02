from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
import datetime
from personnel.models import Division, DivisionStatusUpdate, DivisionType
from notifications.models import Notification
from audit.models import AuditLog

class CheckStatusUpdatesTest(TestCase):

    def setUp(self):
        self.superuser = User.objects.create_superuser(username='admin', password='password', email='admin@example.com')
        self.division1 = Division.objects.create(name='Division 1', division_type=DivisionType.DEPARTMENT)
        self.division2 = Division.objects.create(name='Division 2', division_type=DivisionType.DEPARTMENT)
        self.yesterday = timezone.now().date() - datetime.timedelta(days=1)

    def test_no_overdue_divisions(self):
        """
        Test that the command does nothing if all divisions are up to date.
        """
        DivisionStatusUpdate.objects.create(division=self.division1, update_date=self.yesterday, is_updated=True)
        DivisionStatusUpdate.objects.create(division=self.division2, update_date=self.yesterday, is_updated=True)

        out = StringIO()
        call_command('check_status_updates', stdout=out)

        self.assertIn('All divisions are up to date', out.getvalue())
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_one_overdue_division(self):
        """
        Test that the command creates a notification and audit log for one overdue division.
        """
        DivisionStatusUpdate.objects.create(division=self.division1, update_date=self.yesterday, is_updated=True)
        # division2 is not updated

        out = StringIO()
        call_command('check_status_updates', stdout=out)

        self.assertIn('Found 1 overdue divisions', out.getvalue())
        self.assertIn(f'Escalation triggered for division: {self.division2.name}', out.getvalue())
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(AuditLog.objects.count(), 1)

        notification = Notification.objects.first()
        self.assertEqual(notification.recipient, self.superuser)
        self.assertEqual(notification.notification_type, 'ESCALATION')

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action_type, 'ESCALATION')

    def test_no_superusers(self):
        """
        Test that the command handles the case where there are no superusers.
        """
        self.superuser.is_superuser = False
        self.superuser.save()

        out = StringIO()
        err = StringIO()
        call_command('check_status_updates', stdout=out, stderr=err)

        self.assertIn('No superusers found', err.getvalue())
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(AuditLog.objects.count(), 0)
