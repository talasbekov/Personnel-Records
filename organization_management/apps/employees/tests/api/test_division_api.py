import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from organization_management.apps.divisions.models import Division
from organization_management.apps.auth.models import User

@pytest.mark.django_db
class TestDivisionViewSetAPI:
    def test_get_division_list_unauthenticated(self):
        """Тест получения списка подразделений без аутентификации"""
        client = APIClient()
        url = reverse('division-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_division_list_authenticated(self):
        """Тест получения списка подразделений с аутентификацией"""
        division = Division.objects.create(name="Test Division", division_type='OFFICE')
        user = User.objects.create_user(username='testuser', password='password', role=1, division_assignment=division)
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse('division-list')
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) > 0
