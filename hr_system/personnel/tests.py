from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Position, Division, Employee, UserProfile, UserRole, StaffingUnit, DivisionType, Vacancy
from django.core.cache import cache

class PositionAPITest(APITestCase):
    """
    Tests for the Position API. It relies on the data from the seed migration.
    """
    def setUp(self):
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
        self.assertEqual(response.data.get('count'), 20)

    def test_retrieve_position(self):
        """
        Ensure we can retrieve a single position from the seeded data.
        """
        position = Position.objects.get(name="Инспектор")
        url = f'/api/personnel/positions/{position.id}/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), "Инспектор")

    def test_position_list_is_cached(self):
        """
        Test that the position list endpoint is cached.
        """
        url = '/api/personnel/positions/'
        with self.assertNumQueries(1):
            self.client.get(url, format='json')
        with self.assertNumQueries(0):
            self.client.get(url, format='json')

    def test_position_cache_is_invalidated_on_change(self):
        """
        Test that the position cache is invalidated when a position is changed.
        """
        url = '/api/personnel/positions/'
        self.client.get(url, format='json') # Prime the cache

        Position.objects.create(name='New Position', level=100)

        with self.assertNumQueries(1):
            response = self.client.get(url, format='json')
        self.assertEqual(response.data.get('count'), 21)


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
        url = '/api/personnel/divisions/'
        data = {'name': 'Новый департамент', 'division_type': 'DEPARTMENT'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_division_id = response.data.get('id')

        retrieve_url = f'/api/personnel/divisions/{new_division_id}/'
        response = self.client.get(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), 'Новый департамент')

        update_data = {'name': 'Переименованный департамент', 'division_type': 'DEPARTMENT'}
        response = self.client.put(retrieve_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_division_list_is_cached(self):
        """
        Test that the division list endpoint is cached.
        """
        url = '/api/personnel/divisions/'
        with self.assertNumQueries(1):
            self.client.get(url, format='json')
        with self.assertNumQueries(0):
            self.client.get(url, format='json')

    def test_division_cache_is_invalidated_on_change(self):
        """
        Test that the division cache is invalidated when a division is changed.
        """
        url = '/api/personnel/divisions/'
        self.client.get(url, format='json') # Prime the cache

        Division.objects.create(name='New Division', division_type='OFFICE')

        with self.assertNumQueries(1):
            response = self.client.get(url, format='json')
        self.assertEqual(response.data.get('count'), 2)


class CachingTest(APITestCase):
    def test_cache_set_and_get(self):
        """
        Test that we can set and get a value from the cache.
        """
        cache.set('my_key', 'my_value', 30)
        value = cache.get('my_key')
        self.assertEqual(value, 'my_value')


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
        Employee.objects.create(full_name='New Hire', division=self.division1, position=self.position)
        self.assertEqual(self.staffing_unit.vacant_count, 4)


class RateLimitingTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        UserProfile.objects.create(user=self.user, role=UserRole.ROLE_4)

    def test_user_rate_limit(self):
        """
        Ensure that an authenticated user is rate-limited.
        """
        self.client.force_authenticate(user=self.user)
        url = '/api/personnel/divisions/'

        for i in range(101):
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
        senior_position = Position.objects.create(name="Старший", level=10)
        junior_position = Position.objects.create(name="Младший", level=20)

        employee_junior = Employee.objects.create(
            full_name="Боб Младший", position=junior_position, division=self.division
        )
        employee_senior = Employee.objects.create(
            full_name="Алиса Старшая", position=senior_position, division=self.division
        )

        url = '/api/personnel/employees/'
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertGreaterEqual(len(results), 2)

        names_in_response = [emp.get('full_name') for emp in results]
        senior_index = names_in_response.index(employee_senior.full_name)
        junior_index = names_in_response.index(employee_junior.full_name)

        self.assertLess(
            senior_index,
            junior_index,
            "Senior employee should appear before junior employee in the list.",
        )

    def test_employee_crud_lifecycle(self):
        """
        Test creating, retrieving, updating, and deleting an employee.
        """
        url = '/api/personnel/employees/'
        data = {
            'full_name': 'Тестовый Сотрудник',
            'position_id': self.position.id,
            'division_id': self.division.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_employee_id = response.data.get('id')

        retrieve_url = f'/api/personnel/employees/{new_employee_id}/'
        response = self.client.get(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('full_name'), 'Тестовый Сотрудник')

        new_position = Position.objects.create(name="Новая должность", level=100)
        update_data = {
            'full_name': 'Обновленный Сотрудник',
            'position_id': new_position.id,
            'division_id': self.division.id,
        }
        response = self.client.put(retrieve_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(retrieve_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
