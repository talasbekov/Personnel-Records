from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from organization_management.apps.audit.models import AuditLog
from organization_management.apps.divisions.models import Division, DivisionType
from organization_management.apps.auth.models import User, UserRole
from django.utils import timezone
import datetime

class AuditLogAPITest(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.create_user(username='testuser1', password='password')
        cls.user2 = User.objects.create_user(username='testuser2', password='password')
        UserProfile.objects.create(user=cls.user1, role=UserRole.ROLE_4)

        # Create some log entries
        log1 = AuditLog.objects.create(user=cls.user1, action_type='CREATE', ip_address='127.0.0.1')
        log2 = AuditLog.objects.create(user=cls.user2, action_type='UPDATE', ip_address='127.0.0.2')
        log3 = AuditLog.objects.create(user=cls.user1, action_type='DELETE', ip_address='127.0.0.1')

        # Manually set the timestamps
        cls.ts1 = timezone.make_aware(datetime.datetime(2025, 1, 1, 12, 0, 0))
        cls.ts2 = timezone.make_aware(datetime.datetime(2025, 1, 2, 12, 0, 0))
        cls.ts3 = timezone.make_aware(datetime.datetime(2025, 1, 3, 12, 0, 0))
        AuditLog.objects.filter(id=log1.id).update(timestamp=cls.ts1)
        AuditLog.objects.filter(id=log2.id).update(timestamp=cls.ts2)
        AuditLog.objects.filter(id=log3.id).update(timestamp=cls.ts3)


    def setUp(self):
        self.client.force_authenticate(user=self.user1)

    def test_list_audit_logs(self):
        """
        Ensure we can list all audit logs.
        """
        url = '/api/audit/logs/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)

    def test_filter_by_user(self):
        """
        Test filtering logs by user.
        """
        url = f'/api/audit/logs/?user={self.user2.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['user'], 'testuser2')

    def test_filter_by_action_type(self):
        """
        Test filtering logs by action type.
        """
        url = '/api/audit/logs/?action_type=DELETE'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['action_type'], 'DELETE')

    def test_filter_by_ip_address(self):
        """
        Test filtering logs by IP address.
        """
        url = '/api/audit/logs/?ip_address=127.0.0.2'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_filter_by_timestamp_gte(self):
        """
        Test filtering logs by timestamp (greater than or equal to).
        """
        url = f'/api/audit/logs/?timestamp__gte=2025-01-02T00:00:00Z'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)

    def test_sorting_by_timestamp_ascending(self):
        """
        Test sorting logs by timestamp in ascending order.
        """
        url = '/api/audit/logs/?ordering=timestamp'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['action_type'], 'CREATE')

    def test_default_sorting_is_timestamp_descending(self):
        """
        Test that the default sorting is by timestamp descending.
        """
        url = '/api/audit/logs/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['action_type'], 'DELETE')
