from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Position, Division, Employee, UserProfile, UserRole, DivisionType, SecondmentRequest, EmployeeStatusLog, EmployeeStatusType
import datetime

class SecondmentWorkflowTest(APITestCase):
    def setUp(self):
        # --- Divisions ---
        self.dep1 = Division.objects.create(name="Home Department", division_type=DivisionType.DEPARTMENT)
        self.dep2 = Division.objects.create(name="Target Department", division_type=DivisionType.DEPARTMENT)

        # --- Positions ---
        self.pos = Position.objects.create(name="Specialist", level=30)

        # --- Users and Profiles ---
        self.user_role4 = self.create_user_with_role('admin_user', UserRole.ROLE_4)
        self.requester_user = self.create_user_with_role('requester', UserRole.ROLE_5, self.dep1)
        self.approver_user = self.create_user_with_role('approver', UserRole.ROLE_5, self.dep2)

        # --- Employee to be seconded ---
        self.employee = Employee.objects.create(full_name="John Second", position=self.pos, division=self.dep1)

    def create_user_with_role(self, username, role, division=None):
        user = User.objects.create_user(username=username, password='password')
        UserProfile.objects.create(user=user, role=role, division_assignment=division, include_child_divisions=True)
        return user

    def test_create_secondment_request(self):
        """
        Ensure an authorized user can create a secondment request.
        """
        self.client.force_authenticate(user=self.requester_user)
        url = '/api/personnel/secondment-requests/'
        data = {
            'employee_id': self.employee.id,
            'to_division_id': self.dep2.id,
            'date_from': '2025-09-01',
            'reason': 'Project collaboration'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertEqual(response.data['employee']['id'], self.employee.id)
        self.assertEqual(response.data['from_division']['id'], self.dep1.id)
        self.assertEqual(response.data['requested_by']['id'], self.requester_user.id)

    def test_approve_secondment_request(self):
        """
        Ensure an authorized user can approve a request, which then creates a status log.
        """
        # First, create a pending request
        request = SecondmentRequest.objects.create(
            employee=self.employee,
            from_division=self.dep1,
            to_division=self.dep2,
            date_from='2025-09-01',
            requested_by=self.requester_user
        )

        # The approver from the target division logs in
        self.client.force_authenticate(user=self.approver_user)
        url = f'/api/personnel/secondment-requests/{request.id}/approve/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'APPROVED')
        self.assertEqual(response.data['approved_by']['id'], self.approver_user.id)

        # Verify that the corresponding EmployeeStatusLog was created
        log_exists = EmployeeStatusLog.objects.filter(
            employee=self.employee,
            status=EmployeeStatusType.SECONDED_OUT,
            secondment_division=self.dep2
        ).exists()
        self.assertTrue(log_exists, "Approving a request should create a SECONDED_OUT status log.")

    def test_unauthorized_user_cannot_approve(self):
        """
        Ensure a user not associated with the target division cannot approve.
        """
        request = SecondmentRequest.objects.create(
            employee=self.employee, from_division=self.dep1, to_division=self.dep2,
            date_from='2025-09-01', requested_by=self.requester_user
        )

        # The original requester tries to self-approve, which should be forbidden
        # (This requires adding the permission logic to the view)
        self.client.force_authenticate(user=self.requester_user)
        url = f'/api/personnel/secondment-requests/{request.id}/approve/'
        response = self.client.post(url)
        # This user is from the wrong department and should not be able to approve.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
