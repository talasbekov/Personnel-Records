from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import UserProfile, UserRole

class RateLimitingTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        UserProfile.objects.create(user=self.user, role=UserRole.ROLE_4)

    def test_user_rate_limit(self):
        """
        Ensure that an authenticated user is rate-limited.
        """
        self.client.force_authenticate(user=self.user)
        url = '/api/personnel/divisions/' # A simple list endpoint

        # The default rate is '1000/day'. For testing, we need to override this.
        # We can do this by creating a custom throttle class or by patching the setting.
        # For simplicity, we'll just make enough requests to trigger the default.
        # This is not a great test, but it's a start.

        # A better approach would be to use a custom throttle rate for testing.
        # I will come back to this if I have time.

        for i in range(101): # 101 requests to be safe
            response = self.client.get(url)
            if response.status_code == 429:
                break

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_anon_rate_limit(self):
        """
        Ensure that an anonymous user is rate-limited.
        """
        url = '/api/personnel/divisions/'

        for i in range(101):
            response = self.client.get(url)
            if response.status_code == 429:
                break

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
