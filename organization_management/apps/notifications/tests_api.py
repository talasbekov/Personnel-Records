from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from .models import Notification, NotificationType
from organization_management.apps.auth.models import User, UserRole

class NotificationAPITest(APITestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(username='testuser1', password='password')
        self.user2 = User.objects.create_user(username='testuser2', password='password')
        UserProfile.objects.create(user=self.user1, role=UserRole.ROLE_4)

        # Notification for user1
        self.notification1 = Notification.objects.create(
            recipient=self.user1,
            notification_type=NotificationType.SECONDMENT,
            title='Notification 1',
            message='This is for user 1'
        )
        # Notification for user2
        Notification.objects.create(
            recipient=self.user2,
            notification_type=NotificationType.STATUS_UPDATE,
            title='Notification 2',
            message='This is for user 2'
        )

    def test_list_notifications_for_authenticated_user(self):
        """
        Ensure that the list view only returns notifications for the authenticated user.
        """
        self.client.force_authenticate(user=self.user1)
        url = '/api/notifications/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Notification 1')

    def test_mark_notification_as_read(self):
        """
        Ensure that a notification can be marked as read.
        """
        self.client.force_authenticate(user=self.user1)
        self.assertFalse(self.notification1.is_read)

        url = f'/api/notifications/{self.notification1.id}/mark_as_read/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, 204)
        self.notification1.refresh_from_db()
        self.assertTrue(self.notification1.is_read)
        self.assertIsNotNone(self.notification1.read_at)

    def test_unauthenticated_user_cannot_access_api(self):
        """
        Ensure that unauthenticated users receive a 401 Unauthorized response.
        """
        url = '/api/notifications/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)
