from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Position, Division, Employee, UserProfile, UserRole

class PositionAPITest(APITestCase):
    """
    Tests for the Position API. It relies on the data from the seed migration.
    """
    def setUp(self):
        # We need a user to authenticate
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        UserProfile.objects.create(user=self.user, role=UserRole.ROLE_4)
        self.client.force_authenticate(user=self.user)

    def test_list_positions(self):
        """
        Ensure we can list all 20 seeded positions.
        """
        url = '/api/personnel/positions/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assuming the migration has run, we should have 20 positions
        self.assertEqual(response.data['count'], 20)

    def test_retrieve_position(self):
        """
        Ensure we can retrieve a single position from the seeded data.
        """
        # Get a known position from the migration data
        position = Position.objects.get(name="Инспектор")
        url = f'/api/personnel/positions/{position.id}/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Инспектор")


class DivisionEmployeeAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        UserProfile.objects.create(user=self.user, role=UserRole.ROLE_4)
        self.client.force_authenticate(user=self.user)

        self.position = Position.objects.create(name="Тестовая должность", level=99)
        self.division = Division.objects.create(name="Тестовый отдел", division_type="OFFICE")

    def test_division_crud_lifecycle(self):
        """
        Test creating, retrieving, updating, and deleting a division.
        """
        # 1. Create
        url = '/api/personnel/divisions/'
        data = {'name': 'Новый департамент', 'division_type': 'DEPARTMENT'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Новый департамент')
        new_division_id = response.data['id']

        # 2. Retrieve
        retrieve_url = f'/api/personnel/divisions/{new_division_id}/'
        response = self.client.get(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Новый департамент')

        # 3. Update
        update_data = {'name': 'Переименованный департамент', 'division_type': 'DEPARTMENT'}
        response = self.client.put(retrieve_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Переименованный департамент')

        # 4. Delete
        response = self.client.delete(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify it's gone
        response = self.client.get(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_crud_lifecycle(self):
        """
        Test creating, retrieving, updating, and deleting an employee.
        """
        # 1. Create
        url = '/api/personnel/employees/'
        data = {
            'full_name': 'Тестовый Сотрудник',
            'position_id': self.position.id,
            'division_id': self.division.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['full_name'], 'Тестовый Сотрудник')
        new_employee_id = response.data['id']

        # 2. Retrieve
        retrieve_url = f'/api/personnel/employees/{new_employee_id}/'
        response = self.client.get(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['full_name'], 'Тестовый Сотрудник')
        self.assertEqual(response.data['position']['name'], self.position.name)

        # 3. Update
        new_position = Position.objects.create(name="Новая должность", level=100)
        update_data = {
            'full_name': 'Обновленный Сотрудник',
            'position_id': new_position.id,
            'division_id': self.division.id
        }
        response = self.client.put(retrieve_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['full_name'], 'Обновленный Сотрудник')
        self.assertEqual(response.data['position']['name'], new_position.name)

        # 4. Delete
        response = self.client.delete(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
