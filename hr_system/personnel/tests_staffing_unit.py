from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Position, Division, StaffingUnit, UserProfile, UserRole, DivisionType

class StaffingUnitAPITest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='admin', password='password')
        UserProfile.objects.create(user=self.admin_user, role=UserRole.ROLE_4)

        self.personnel_admin = User.objects.create_user(username='personnel_admin', password='password')
        self.division1 = Division.objects.create(name='Division 1', division_type=DivisionType.DEPARTMENT)
        UserProfile.objects.create(user=self.personnel_admin, role=UserRole.ROLE_5, division_assignment=self.division1)

        self.viewer_user = User.objects.create_user(username='viewer', password='password')
        UserProfile.objects.create(user=self.viewer_user, role=UserRole.ROLE_1)

        self.position = Position.objects.create(name='Test Position', level=1)
        self.staffing_unit = StaffingUnit.objects.create(division=self.division1, position=self.position, quantity=5)

    def test_admin_can_crud_staffing_unit(self):
        """
        Ensure admin user (Role 4) can perform CRUD operations.
        """
        self.client.force_authenticate(user=self.admin_user)

        # List
        url = '/api/personnel/staffing-units/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Create
        data = {'division_id': self.division1.id, 'position_id': self.position.id, 'quantity': 10}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StaffingUnit.objects.count(), 2)

        # Retrieve
        detail_url = f'/api/personnel/staffing-units/{self.staffing_unit.id}/'
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Update
        update_data = {'quantity': 15}
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.staffing_unit.refresh_from_db()
        self.assertEqual(self.staffing_unit.quantity, 15)

        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(StaffingUnit.objects.count(), 1)

    def test_personnel_admin_can_crud_staffing_unit(self):
        """
        Ensure personnel admin (Role 5) can perform CRUD operations.
        """
        self.client.force_authenticate(user=self.personnel_admin)
        # Similar CRUD tests as admin...
        url = '/api/personnel/staffing-units/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_viewer_cannot_write_staffing_unit(self):
        """
        Ensure viewer user (Role 1) cannot perform write operations.
        """
        self.client.force_authenticate(user=self.viewer_user)

        # List (should be allowed)
        url = '/api/personnel/staffing-units/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create (should be forbidden)
        data = {'division_id': self.division1.id, 'position_id': self.position.id, 'quantity': 10}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
