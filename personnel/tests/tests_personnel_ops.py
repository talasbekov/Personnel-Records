from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Position, Division, Employee, UserProfile, UserRole, DivisionType
import datetime

class PersonnelOperationsTest(APITestCase):
    def setUp(self):
        # --- Divisions ---
        self.dep1 = Division.objects.create(name="Department 1", division_type=DivisionType.DEPARTMENT)
        self.man1 = Division.objects.create(name="Management 1.1", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)
        self.man2 = Division.objects.create(name="Management 1.2", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)
        self.dep2 = Division.objects.create(name="Department 2", division_type=DivisionType.DEPARTMENT)

        # --- Positions ---
        self.pos = Position.objects.create(name="Operator", level=30)

        # --- Users and Profiles ---
        self.user_role4 = self.create_user_with_role('admin_user', UserRole.ROLE_4)
        self.user_role5 = self.create_user_with_role('hr_user_dep1', UserRole.ROLE_5, self.dep1)
        self.user_role3 = self.create_user_with_role('manager_user', UserRole.ROLE_3, self.man1)

        # --- Employees ---
        self.emp1 = Employee.objects.create(full_name="Emp To Terminate", position=self.pos, division=self.man1)
        self.emp2 = Employee.objects.create(full_name="Emp To Transfer", position=self.pos, division=self.man1)
        self.emp3 = Employee.objects.create(full_name="Emp Outside Scope", position=self.pos, division=self.dep2)

    def create_user_with_role(self, username, role, division=None):
        user = User.objects.create_user(username=username, password='password')
        UserProfile.objects.create(user=user, role=role, division_assignment=division, include_child_divisions=True)
        return user

    # --- Terminate Tests ---
    def test_role4_can_terminate_employee(self):
        self.client.force_authenticate(user=self.user_role4)
        url = f'/api/personnel/employees/{self.emp1.id}/terminate/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.emp1.refresh_from_db()
        self.assertFalse(self.emp1.is_active)
        self.assertEqual(self.emp1.fired_date, datetime.date.today())

    def test_role5_can_terminate_employee_in_scope(self):
        self.client.force_authenticate(user=self.user_role5)
        url = f'/api/personnel/employees/{self.emp1.id}/terminate/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_role5_cannot_terminate_employee_out_of_scope(self):
        self.client.force_authenticate(user=self.user_role5)
        url = f'/api/personnel/employees/{self.emp3.id}/terminate/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND) # 404 because get_object() will fail

    def test_role3_cannot_terminate_employee(self):
        self.client.force_authenticate(user=self.user_role3)
        url = f'/api/personnel/employees/{self.emp1.id}/terminate/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Transfer Tests ---
    def test_role4_can_transfer_employee(self):
        self.client.force_authenticate(user=self.user_role4)
        url = f'/api/personnel/employees/{self.emp2.id}/transfer/'
        response = self.client.post(url, {'new_division_id': self.dep2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.emp2.refresh_from_db()
        self.assertEqual(self.emp2.division, self.dep2)

    def test_role5_can_transfer_employee_in_scope(self):
        self.client.force_authenticate(user=self.user_role5)
        url = f'/api/personnel/employees/{self.emp2.id}/transfer/'
        response = self.client.post(url, {'new_division_id': self.man2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.emp2.refresh_from_db()
        self.assertEqual(self.emp2.division, self.man2)

    def test_role5_cannot_transfer_employee_out_of_scope(self):
        self.client.force_authenticate(user=self.user_role5)
        url = f'/api/personnel/employees/{self.emp2.id}/transfer/'
        response = self.client.post(url, {'new_division_id': self.dep2.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
