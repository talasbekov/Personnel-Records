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

        # 4. Delete
        response = self.client.delete(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_prevent_cyclical_division_dependency(self):
        """
        Test that creating a cyclical dependency in divisions is not allowed.
        """
        parent = Division.objects.create(name="Parent", division_type="DEPARTMENT")
        child = Division.objects.create(name="Child", parent_division=parent, division_type="MANAGEMENT")

        url = f'/api/personnel/divisions/{parent.id}/'
        data = {'name': 'Parent Updated', 'division_type': 'DEPARTMENT', 'parent_division_id': child.id}
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Expect an error about setting a child as its own parent / cyclical relationship
        self.assertIn("children as its parent", response.data.get('non_field_errors', [''])[0])

    def test_prevent_deleting_division_with_children(self):
        """
        Test that a division with child divisions cannot be deleted.
        """
        parent = Division.objects.create(name="Parent", division_type="DEPARTMENT")
        Division.objects.create(name="Child", parent_division=parent, division_type="MANAGEMENT")

        url = f'/api/personnel/divisions/{parent.id}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("has child divisions", response.data.get('error', ''))

    def test_prevent_deleting_division_with_employees(self):
        """
        Test that a division with employees cannot be deleted (db-level protection).
        """
        div_with_emp = Division.objects.create(name="Busy Division", division_type="OFFICE")
        Employee.objects.create(full_name="John Doe", position=self.position, division=div_with_emp)

        url = f'/api/personnel/divisions/{div_with_emp.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("has employees assigned", response.data.get('error', ''))

    def test_employee_list_is_sorted_by_position_level(self):
        """
        Ensure the employee list is sorted by position level (hierarchy).
        """
        # Create positions with different levels
        senior_position = Position.objects.create(name="Старший", level=10)
        junior_position = Position.objects.create(name="Младший", level=20)

        # Create employees in a non-alphabetical, non-chronологическом order
        employee_junior = Employee.objects.create(full_name="Боб Младший", position=junior_position, division=self.division)
        employee_senior = Employee.objects.create(full_name="Алиса Старшая", position=senior_position, division=self.division)

        # Fetch the list of employees
        url = '/api/personnel/employees/'
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data.get('results', [])
        self.assertGreaterEqual(len(results), 2)

        names_in_response = [emp['full_name'] for emp in results]
        senior_index = names_in_response.index(employee_senior.full_name)
        junior_index = names_in_response.index(employee_junior.full_name)

        # Assert that the senior employee appears before the junior one
        self.assertLess(senior_index, junior_index, "Senior employee should appear before junior employee in the list.")

    def test_employee_crud_lifecycle(self):
        """
        Test creating, retrieving, updating, and deleting an employee.
        """
        url = '/api/personnel/employees/'
        data = {'full_name': 'Тестовый Сотрудник', 'position_id': self.position.id, 'division_id': self.division.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_employee_id = response.data['id']

        retrieve_url = f'/api/personnel/employees/{new_employee_id}/'
        response = self.client.get(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['full_name'], 'Тестовый Сотрудник')

        new_position = Position.objects.create(name="Новая должность", level=100)
        update_data = {'full_name': 'Обновленный Сотрудник', 'position_id': new_position.id, 'division_id': self.division.id}
        response = self.client.put(retrieve_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
