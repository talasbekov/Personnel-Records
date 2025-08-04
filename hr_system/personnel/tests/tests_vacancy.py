from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Position, Division, StaffingUnit, UserProfile, UserRole, DivisionType, Vacancy

class VacancyAPITest(APITestCase):
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
        self.vacancy = Vacancy.objects.create(staffing_unit=self.staffing_unit, title='Test Vacancy', created_by=self.admin_user)

    def test_admin_can_crud_vacancy(self):
        """
        Ensure admin user (Role 4) can perform CRUD operations on vacancies.
        """
        self.client.force_authenticate(user=self.admin_user)

        # List
        url = '/api/personnel/vacancies/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Create
        data = {'staffing_unit_id': self.staffing_unit.id, 'title': 'New Test Vacancy'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vacancy.objects.count(), 2)

        # Retrieve
        detail_url = f'/api/personnel/vacancies/{self.vacancy.id}/'
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Update
        update_data = {'title': 'Updated Vacancy Title'}
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.vacancy.refresh_from_db()
        self.assertEqual(self.vacancy.title, 'Updated Vacancy Title')

        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Vacancy.objects.count(), 1)

    def test_viewer_cannot_write_vacancy(self):
        """
        Ensure viewer user (Role 1) cannot perform write operations on vacancies.
        """
        self.client.force_authenticate(user=self.viewer_user)

        url = '/api/personnel/vacancies/'
        # Create (should be forbidden)
        data = {'staffing_unit_id': self.staffing_unit.id, 'title': 'New Test Vacancy'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_vacancy_calculation(self):
        """
        Test that the vacant_count on the StaffingUnit is correct.
        """
        self.assertEqual(self.staffing_unit.vacant_count, 5)

        # Create a vacancy, shouldn't change vacant_count
        Vacancy.objects.create(staffing_unit=self.staffing_unit, title='Another Vacancy')
        self.assertEqual(self.staffing_unit.vacant_count, 5)

        # Hire an employee, should decrease vacant_count
        from .models import Employee
        Employee.objects.create(full_name='New Hire', division=self.division1, position=self.position)
        self.assertEqual(self.staffing_unit.vacant_count, 4)
