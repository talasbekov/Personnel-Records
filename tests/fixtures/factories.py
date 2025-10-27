import factory
from factory.django import DjangoModelFactory
from organization_management.apps.auth.models import User
from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.models import Employee
from organization_management.apps.dictionaries.models import Position

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'password')

class PositionFactory(DjangoModelFactory):
    class Meta:
        model = Position

    name = factory.Sequence(lambda n: f'Position {n}')

class DivisionFactory(DjangoModelFactory):
    class Meta:
        model = Division

    name = factory.Sequence(lambda n: f'Division {n}')
    code = factory.Sequence(lambda n: f'div{n}')
    division_type = Division.DivisionType.DEPARTMENT

class EmployeeFactory(DjangoModelFactory):
    class Meta:
        model = Employee

    personnel_number = factory.Sequence(lambda n: f'PN{n}')
    last_name = factory.Faker('last_name')
    first_name = factory.Faker('first_name')
    birth_date = factory.Faker('date_of_birth')
    gender = 'M'
    division = factory.SubFactory(DivisionFactory)
    position = factory.SubFactory(PositionFactory)
    hire_date = factory.Faker('date')
