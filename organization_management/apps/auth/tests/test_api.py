import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from organization_management.apps.auth.models import User, UserRole
from organization_management.apps.divisions.models import Division

@pytest.mark.django_db
class TestAuthAPI:

    def setup_method(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin',
            password='password',
            role=UserRole.ROLE_4
        )
        self.division = Division.objects.create(name="Test Division", division_type="OFFICE")
        self.regular_user = User.objects.create_user(
            username='user',
            password='password',
            role=UserRole.ROLE_1,
            division_assignment=self.division
        )

    def test_login_success(self):
        """Тест успешного входа в систему и получения токена"""
        url = reverse('token_obtain_pair')
        response = self.client.post(url, {'username': 'admin', 'password': 'password'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'token' in response.data

    def test_login_fail(self):
        """Тест неудачного входа с неверными данными"""
        url = reverse('token_obtain_pair')
        response = self.client.post(url, {'username': 'admin', 'password': 'wrongpassword'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_list_access_for_admin(self):
        """Тест: админ (Роль-4) может получить список пользователей"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('user-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_user_list_denied_for_regular_user(self):
        """Тест: обычный пользователь не может получить список пользователей"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('user-list')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_user_by_admin(self):
        """Тест: админ может создать нового пользователя"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('user-list')
        data = {
            'username': 'newuser',
            'password': 'newpassword',
            'role': UserRole.ROLE_1,
            'division_assignment': self.division.id
        }
        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.count() == 3

    def test_update_user_by_admin(self):
        """Тест: админ может обновить данные пользователя"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('user-detail', kwargs={'pk': self.regular_user.pk})
        data = {'first_name': 'Updated'}
        response = self.client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        self.regular_user.refresh_from_db()
        assert self.regular_user.first_name == 'Updated'

    def test_delete_user_by_admin(self):
        """Тест: админ может удалить пользователя"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('user-detail', kwargs={'pk': self.regular_user.pk})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert User.objects.count() == 1

    def test_user_viewset_permissions(self):
        """Тест: доступ к UserViewSet есть только у Роли-4"""
        users = {
            'role1': self.regular_user,
            'role4': self.admin_user
        }

        for role, user in users.items():
            self.client.force_authenticate(user=user)
            url = reverse('user-list')
            response = self.client.get(url)
            if role == 'role4':
                assert response.status_code == status.HTTP_200_OK
            else:
                assert response.status_code == status.HTTP_403_FORBIDDEN
