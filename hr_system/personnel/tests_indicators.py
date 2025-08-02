from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Division, DivisionType, DivisionStatusUpdate, UserProfile, UserRole
import datetime

class IndicatorLogicTest(APITestCase):
    def setUp(self):
        # --- Create Users ---
        self.admin_user = User.objects.create_user(username='admin', password='password')
        UserProfile.objects.create(user=self.admin_user, role=UserRole.ROLE_4)

        # --- Create Divisions ---
        self.dep1 = Division.objects.create(name="Department 1", division_type=DivisionType.DEPARTMENT)
        self.man1 = Division.objects.create(name="Management 1.1", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)
        self.man2 = Division.objects.create(name="Management 1.2", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)
        self.man3 = Division.objects.create(name="Management 1.3", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)

        self.dep2 = Division.objects.create(name="Department 2", division_type=DivisionType.DEPARTMENT)
        self.man4 = Division.objects.create(name="Management 2.1", division_type=DivisionType.MANAGEMENT, parent_division=self.dep2)
        self.man5 = Division.objects.create(name="Management 2.2", division_type=DivisionType.MANAGEMENT, parent_division=self.dep2)

        self.dep3 = Division.objects.create(name="Department 3 (All Red)", division_type=DivisionType.DEPARTMENT)
        self.man6 = Division.objects.create(name="Management 3.1", division_type=DivisionType.MANAGEMENT, parent_division=self.dep3)

        # --- Create Status Updates for a specific date ---
        self.test_date = datetime.date(2025, 8, 1)

        # Department 1 will be YELLOW (1 of 3 updated)
        DivisionStatusUpdate.objects.create(division=self.man1, update_date=self.test_date, is_updated=True)
        # man2 and man3 are not updated

        # Department 2 will be GREEN (2 of 2 updated)
        DivisionStatusUpdate.objects.create(division=self.man4, update_date=self.test_date, is_updated=True)
        DivisionStatusUpdate.objects.create(division=self.man5, update_date=self.test_date, is_updated=True)

        # Department 3 will be RED (0 of 1 updated)
        # No update for man6

    def test_status_summary_endpoint(self):
        """
        Tests the logic of the status-summary endpoint with a mix of statuses.
        """
        self.client.force_authenticate(user=self.admin_user)
        url = f'/api/personnel/divisions/status-summary/?date={self.test_date.isoformat()}'

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The response is a list of root divisions (the departments)
        summary_data = response.data
        self.assertEqual(len(summary_data), 3)

        # Find the data for each department
        dep1_data = next((d for d in summary_data if d['id'] == self.dep1.id), None)
        dep2_data = next((d for d in summary_data if d['id'] == self.dep2.id), None)
        dep3_data = next((d for d in summary_data if d['id'] == self.dep3.id), None)

        self.assertIsNotNone(dep1_data)
        self.assertIsNotNone(dep2_data)
        self.assertIsNotNone(dep3_data)

        # --- Assert Department 1 (Yellow) ---
        self.assertEqual(dep1_data['indicator'], 'YELLOW')
        self.assertEqual(dep1_data['total_children'], 3)
        self.assertEqual(dep1_data['updated_children'], 1)
        man1_data = next((m for m in dep1_data['children'] if m['id'] == self.man1.id), None)
        man2_data = next((m for m in dep1_data['children'] if m['id'] == self.man2.id), None)
        self.assertEqual(man1_data['indicator'], 'GREEN')
        self.assertEqual(man2_data['indicator'], 'RED')

        # --- Assert Department 2 (Green) ---
        self.assertEqual(dep2_data['indicator'], 'GREEN')
        self.assertEqual(dep2_data['total_children'], 2)
        self.assertEqual(dep2_data['updated_children'], 2)

        # --- Assert Department 3 (Red) ---
        self.assertEqual(dep3_data['indicator'], 'RED')
        self.assertEqual(dep3_data['total_children'], 1)
        self.assertEqual(dep3_data['updated_children'], 0)
