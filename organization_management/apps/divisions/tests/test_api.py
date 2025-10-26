import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from organization_management.apps.auth.models import User
from organization_management.apps.divisions.models import Division

@pytest.mark.django_db
class TestDivisionAPI:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='password', role=1)
        self.client.force_authenticate(user=self.user)
        self.division = Division.objects.create(name="Test Division", code="TD01", division_type='division')

    def test_get_division_list(self):
        """Тест получения списка подразделений"""
        url = reverse('division-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) > 0

    def test_get_division_tree(self):
        """Тест получения дерева подразделений"""
        url = reverse('division-tree')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_create_division(self):
        """Тест создания подразделения"""
        url = reverse('division-list')
        data = {'name': 'New Division', 'code': 'ND01', 'division_type': 'division'}
        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Division.objects.count() == 2
