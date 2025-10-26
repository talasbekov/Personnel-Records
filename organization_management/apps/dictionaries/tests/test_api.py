import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from organization_management.apps.auth.models import User, UserRole
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.divisions.models import Division

@pytest.mark.django_db
class TestDictionariesAPI:
    def setup_method(self):
        self.client = APIClient()
        self.division = Division.objects.create(name="Test Division", code="TD01", division_type='division')
        self.admin_user = User.objects.create_user(username='admin', password='password', role=UserRole.ROLE_4)
        self.hr_user = User.objects.create_user(username='hr', password='password', role=UserRole.ROLE_5, division_assignment=self.division)
        self.regular_user = User.objects.create_user(username='user', password='password', role=UserRole.ROLE_1, division_assignment=self.division)
        self.position = Position.objects.create(name='Тестовая должность', level=1)

    def test_unauthenticated_access_denied(self):
        """Тест: неаутентифицированный пользователь не имеет доступа"""
        url = reverse('position-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_regular_user_access_denied(self):
        """Тест: пользователь с неавторизованной ролью не имеет доступа"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('position-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_user_has_access(self):
        """Тест: админ (Роль-4) имеет доступ к списку должностей"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('position-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) > 0

    def test_hr_user_can_create_position(self):
        """Тест: HR (Роль-5) может создать новую должность"""
        self.client.force_authenticate(user=self.hr_user)
        url = reverse('position-list')
        data = {'name': 'Новая должность', 'level': 2}
        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Position.objects.count() == 2

    def test_admin_can_delete_position(self):
        """Тест: админ (Роль-4) может удалить должность"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('position-detail', kwargs={'pk': self.position.pk})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Position.objects.count() == 0
