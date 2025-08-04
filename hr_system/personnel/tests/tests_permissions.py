from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Position, Division, Employee, UserProfile, UserRole, DivisionType, EmployeeStatusType, EmployeeStatusLog

class PermissionsTest(APITestCase):
    def setUp(self):
        # Create a hierarchy of divisions
        self.company = Division.objects.create(name="Company", division_type=DivisionType.COMPANY)
        self.dep1 = Division.objects.create(name="Department 1", division_type=DivisionType.DEPARTMENT, parent_division=self.company)
        self.dep2 = Division.objects.create(name="Department 2", division_type=DivisionType.DEPARTMENT, parent_division=self.company)
        self.man1_dep1 = Division.objects.create(name="Management 1.1", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)
        self.off1_man1_dep1 = Division.objects.create(name="Office 1.1.1", division_type=DivisionType.OFFICE, parent_division=self.man1_dep1)

        # Create positions
        self.pos1 = Position.objects.create(name="Manager", level=10)
        self.pos2 = Position.objects.create(name="Clerk", level=20)

        # Create users for each role
        self.user_role1 = self.create_user_with_role('user_role1', UserRole.ROLE_1)
        self.user_role2 = self.create_user_with_role('user_role2', UserRole.ROLE_2, self.dep1)
        self.user_role3 = self.create_user_with_role('user_role3', UserRole.ROLE_3, self.man1_dep1)
        self.user_role4 = self.create_user_with_role('user_role4', UserRole.ROLE_4)
        self.user_role5 = self.create_user_with_role('user_role5', UserRole.ROLE_5, self.dep1)
        self.user_role6 = self.create_user_with_role('user_role6', UserRole.ROLE_6, self.off1_man1_dep1)

        # Create employees and link them to the users where necessary for tests
        self.emp_dep1 = Employee.objects.create(full_name="Emp Dep1", position=self.pos1, division=self.dep1)
        self.emp_dep2 = Employee.objects.create(full_name="Emp Dep2", position=self.pos2, division=self.dep2)
        self.emp_man1_dep1 = Employee.objects.create(full_name="Emp Man1", position=self.pos1, division=self.man1_dep1, user=self.user_role3) # Linked for seconded-out test
        self.emp_off1_man1_dep1 = Employee.objects.create(full_name="Emp Off1", position=self.pos2, division=self.off1_man1_dep1)


    def create_user_with_role(self, username, role, division=None):
        user = User.objects.create_user(username=username, password='password')
        UserProfile.objects.create(user=user, role=role, division_assignment=division, include_child_divisions=True)
        return user

    def test_role1_permissions(self):
        self.client.force_authenticate(user=self.user_role1)
        response = self.client.get('/api/personnel/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)
        response = self.client.post('/api/personnel/employees/', {'full_name': 'New', 'position_id': self.pos1.id, 'division_id': self.dep1.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_role2_permissions(self):
        self.client.force_authenticate(user=self.user_role2)
        response = self.client.get('/api/personnel/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3) # emp_dep1, emp_man1_dep1, emp_off1_man1_dep1
        self.assertNotIn(self.emp_dep2.full_name, [e['full_name'] for e in response.data['results']])
        response = self.client.post('/api/personnel/employees/', {'full_name': 'New', 'position_id': self.pos1.id, 'division_id': self.dep1.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_role4_permissions(self):
        self.client.force_authenticate(user=self.user_role4)
        response = self.client.get('/api/personnel/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)
        response = self.client.post('/api/personnel/employees/', {'full_name': 'New by Admin', 'position_id': self.pos1.id, 'division_id': self.dep1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_role5_permissions(self):
        self.client.force_authenticate(user=self.user_role5)
        response = self.client.get('/api/personnel/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
        response = self.client.post('/api/personnel/employees/', {'full_name': 'New by HR', 'position_id': self.pos1.id, 'division_id': self.man1_dep1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post('/api/personnel/employees/', {'full_name': 'New by HR Invalid', 'position_id': self.pos1.id, 'division_id': self.dep2.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_role5_scoping_with_include_child_divisions_false(self):
        self.user_role5.profile.include_child_divisions = False
        self.user_role5.profile.save()
        self.client.force_authenticate(user=self.user_role5)
        response = self.client.get('/api/personnel/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see employees in the directly assigned division (dep1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['full_name'], self.emp_dep1.full_name)

    def test_role3_loses_permission_when_seconded_out(self):
        EmployeeStatusLog.objects.create(
            employee=self.emp_man1_dep1, # This employee is linked to user_role3
            status=EmployeeStatusType.SECONDED_OUT,
            date_from='2025-01-01',
            created_by=self.user_role4
        )
        self.client.force_authenticate(user=self.user_role3)
        url = f'/api/personnel/divisions/{self.man1_dep1.id}/update-statuses/'
        data = [{'employee_id': self.emp_man1_dep1.id, 'status': 'ON_LEAVE', 'date_from': '2025-02-01'}]
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StatusUpdateTest(APITestCase):
    def setUp(self):
        self.company = Division.objects.create(name="Company", division_type=DivisionType.COMPANY)
        self.dep1 = Division.objects.create(name="Department 1", division_type=DivisionType.DEPARTMENT, parent_division=self.company)
        self.man1_dep1 = Division.objects.create(name="Management 1.1", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)
        self.pos1 = Position.objects.create(name="Manager", level=10)
        self.emp1 = Employee.objects.create(full_name="Emp1", position=self.pos1, division=self.man1_dep1)
        self.emp2 = Employee.objects.create(full_name="Emp2", position=self.pos1, division=self.man1_dep1)
        self.user_role3 = User.objects.create_user(username='user_role3', password='password')
        UserProfile.objects.create(user=self.user_role3, role=UserRole.ROLE_3, division_assignment=self.man1_dep1)

    def test_successful_status_update(self):
        self.client.force_authenticate(user=self.user_role3)
        url = f'/api/personnel/divisions/{self.man1_dep1.id}/update-statuses/'
        data = [
            {'employee_id': self.emp1.id, 'status': 'ON_LEAVE', 'date_from': '2025-01-01', 'date_to': '2025-01-10'},
            {'employee_id': self.emp2.id, 'status': 'SICK_LEAVE', 'date_from': '2025-01-05'}
        ]
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EmployeeStatusLog.objects.count(), 2)
        self.assertEqual(EmployeeStatusLog.objects.get(employee=self.emp1).status, 'ON_LEAVE')

    def test_unauthorized_status_update(self):
        user_unauthorized = User.objects.create_user(username='unauthorized', password='password')
        UserProfile.objects.create(user=user_unauthorized, role=UserRole.ROLE_2, division_assignment=self.dep1)
        self.client.force_authenticate(user=user_unauthorized)
        url = f'/api/personnel/divisions/{self.man1_dep1.id}/update-statuses/'
        data = [{'employee_id': self.emp1.id, 'status': 'ON_LEAVE', 'date_from': '2025-01-01'}]
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
