from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from audit.models import AuditLog
from personnel.models import Division, DivisionType, UserProfile, UserRole

class AuditMiddlewareTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        UserProfile.objects.create(user=self.user, role=UserRole.ROLE_4) # Admin role
        self.client.force_authenticate(user=self.user)
        self.division = Division.objects.create(name='Test Division', division_type=DivisionType.DEPARTMENT)

    def test_create_action_is_logged(self):
        """
        Ensure that a POST request that creates an object is logged.
        """
        url = '/api/personnel/divisions/'
        data = {'name': 'New Department', 'division_type': 'DEPARTMENT'}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)

        log_entry = AuditLog.objects.latest('timestamp')
        self.assertEqual(AuditLog.objects.count(), 1)
        self.assertEqual(log_entry.action_type, 'CREATE')
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.content_type.model, 'division')
        self.assertEqual(log_entry.object_id, response.data['id'])

    def test_update_action_is_logged_with_diff(self):
        """
        Ensure that a PUT request that updates an object is logged with a diff.
        """
        url = f'/api/personnel/divisions/{self.division.id}/'
        data = {'name': 'Updated Division Name', 'division_type': 'DEPARTMENT'}

        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(AuditLog.objects.count(), 1)
        log_entry = AuditLog.objects.latest('timestamp')
        self.assertEqual(log_entry.action_type, 'UPDATE')
        self.assertIn('diff', log_entry.payload)
        self.assertEqual(log_entry.payload['diff']['old']['name'], 'Test Division')
        self.assertEqual(log_entry.payload['diff']['new']['name'], 'Updated Division Name')

    def test_delete_action_is_logged(self):
        """
        Ensure that a DELETE request is logged.
        """
        url = f'/api/personnel/divisions/{self.division.id}/'

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

        self.assertEqual(AuditLog.objects.count(), 1)
        log_entry = AuditLog.objects.latest('timestamp')
        self.assertEqual(log_entry.action_type, 'DELETE')
        self.assertEqual(str(log_entry.object_id), str(self.division.id))

    def test_get_request_is_not_logged(self):
        """
        Ensure that GET requests are not logged.
        """
        url = f'/api/personnel/divisions/'
        self.client.get(url)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_non_api_request_is_not_logged(self):
        """
        Ensure that requests to non-API URLs are not logged.
        """
        # This assumes there's a non-API URL at '/'.
        # If not, this test would need a valid non-API URL.
        self.client.post('/', {'data': 'some_data'})
        self.assertEqual(AuditLog.objects.count(), 0)
