import pytest
from rest_framework.test import APIClient
from rest_framework import status
from tests.fixtures.factories import EmployeeFactory, UserFactory

@pytest.mark.django_db
class TestEmployeeViewSet:
    def test_get_employees_list(self):
        """
        Тест успешного получения списка сотрудников.
        """
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        EmployeeFactory.create_batch(5)

        response = client.get('/api/employees/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5
