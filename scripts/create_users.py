# create_users.py
# Запустите этот скрипт через Django shell: python manage.py shell < create_users.py

from django.contrib.auth.models import User
from personnel.models import UserProfile, Division, Position, Employee, UserRole, DivisionType

# Создаем суперпользователя (если еще нет)
if not User.objects.filter(username='admin').exists():
    admin_user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123',
        first_name='Admin',
        last_name='System'
    )
    print("Создан суперпользователь: admin / admin123")
else:
    admin_user = User.objects.get(username='admin')
    print("Суперпользователь admin уже существует")

# Создаем тестового пользователя 'erda'
if not User.objects.filter(username='erda').exists():
    erda_user = User.objects.create_user(
        username='erda',
        email='erda@example.com',
        password='string',  # Пароль как в вашем запросе
        first_name='Erda',
        last_name='Test'
    )
    print("Создан пользователь: erda / string")
else:
    erda_user = User.objects.get(username='erda')
    print("Пользователь erda уже существует")

# Создаем организационную структуру (если еще нет)
if not Division.objects.filter(division_type=DivisionType.COMPANY).exists():
    company = Division.objects.create(
        name='Главная компания',
        code='COMP-001',
        division_type=DivisionType.COMPANY,
        description='Головная организация'
    )
    print("Создана компания")
else:
    company = Division.objects.filter(division_type=DivisionType.COMPANY).first()

if not Division.objects.filter(division_type=DivisionType.DEPARTMENT).exists():
    department = Division.objects.create(
        name='IT Департамент',
        code='DEPT-001',
        division_type=DivisionType.DEPARTMENT,
        parent_division=company,
        description='Департамент информационных технологий'
    )
    print("Создан департамент")
else:
    department = Division.objects.filter(division_type=DivisionType.DEPARTMENT).first()

# Создаем должность (если еще нет)
if not Position.objects.exists():
    position = Position.objects.create(
        name='Разработчик',
        level=5,
        description='Разработчик ПО'
    )
    print("Создана должность")
else:
    position = Position.objects.first()

# Создаем профиль для пользователя erda (Роль 3 - может редактировать)
if not hasattr(erda_user, 'profile'):
    profile = UserProfile.objects.create(
        user=erda_user,
        role=UserRole.ROLE_3,  # Просмотр департамента + редактирование управления
        division_assignment=department,
        phone='+7 123 456 7890'
    )
    print(f"Создан профиль для пользователя erda с ролью {UserRole.ROLE_3.label}")
else:
    print("Профиль для пользователя erda уже существует")

# Создаем сотрудника для пользователя erda
if not hasattr(erda_user, 'employee'):
    employee = Employee.objects.create(
        user=erda_user,
        full_name='Erda Test',
        position=position,
        division=department,
        contact_email='erda@example.com',
        is_active=True
    )
    print("Создан сотрудник для пользователя erda")
else:
    print("Сотрудник для пользователя erda уже существует")

print("\n=== Готово! ===")
print("Теперь вы можете войти с учетными данными:")
print("1. admin / admin123 (суперпользователь)")
print("2. erda / string (обычный пользователь с ролью 3)")
