from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from organization_management.apps.divisions.models import Division
DivisionType = Division.DivisionType


class DivisionViewSetTest(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='testuser', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.company = Division.objects.create(name='Test Company', division_type='COMPANY', code='COMPANY')
        self.division = Division.objects.create(name='Test Division', division_type='DEPARTMENT', parent_division=self.company, code='DEPT')

    def test_list_divisions(self):
        response = self.client.get('/api/divisions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_create_division(self):
        data = {'name': 'New Division', 'division_type': 'DEPARTMENT', 'parent_division': self.company.id, 'code': 'DEPT2'}
        response = self.client.post('/api/divisions/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Division.objects.count(), 3)
