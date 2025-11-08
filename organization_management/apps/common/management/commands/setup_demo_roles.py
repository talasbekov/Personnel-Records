"""
Management command для создания демонстрационных ролей и пользователей
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from organization_management.apps.common.models import UserRole
from organization_management.apps.divisions.models import Division


class Command(BaseCommand):
    help = 'Создание демонстрационных ролей и пользователей для тестирования RBAC'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Удалить существующие демо-пользователи перед создание новых',
        )
    
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Удаление существующих демо-пользователей...')
            User.objects.filter(username__startswith='demo_').delete()
            self.stdout.write(self.style.SUCCESS('✓ Демо-пользователи удалены'))
        
        # Получить первое подразделение для примера
        try:
            division = Division.objects.first()
            if not division:
                self.stdout.write(self.style.WARNING('⚠ Нет подразделений в системе. Создайте хотя бы одно подразделение.'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Ошибка при получении подразделения: {e}'))
            return
        
        # Список демо-пользователей
        demo_users = [
            {
                'username': 'demo_observer_org',
                'email': 'observer_org@example.com',
                'password': 'demo123',
                'first_name': 'Наблюдатель',
                'last_name': 'Организации',
                'role': UserRole.RoleType.OBSERVER_ORG,
                'scope_division': None,
            },
            {
                'username': 'demo_admin',
                'email': 'admin@example.com',
                'password': 'demo123',
                'first_name': 'Системный',
                'last_name': 'Администратор',
                'role': UserRole.RoleType.SYS_ADMIN,
                'scope_division': None,
            },
            {
                'username': 'demo_hr_admin',
                'email': 'hr@example.com',
                'password': 'demo123',
                'first_name': 'Кадровый',
                'last_name': 'Администратор',
                'role': UserRole.RoleType.HR_ADMIN,
                'scope_division': division,
            },
        ]
        
        created_count = 0
        for user_data in demo_users:
            try:
                # Создать пользователя
                user, created = User.objects.get_or_create(
                    username=user_data['username'],
                    defaults={
                        'email': user_data['email'],
                        'first_name': user_data['first_name'],
                        'last_name': user_data['last_name'],
                        'is_staff': True,  # Доступ в админку
                    }
                )
                
                if created:
                    user.set_password(user_data['password'])
                    user.save()
                
                # Создать роль
                role, role_created = UserRole.objects.get_or_create(
                    user=user,
                    defaults={
                        'role': user_data['role'],
                        'scope_division': user_data['scope_division'],
                    }
                )
                
                if created and role_created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Создан пользователь: {user.username} ({role.get_role_display()})'
                        )
                    )
                elif created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Создан пользователь: {user.username} (роль уже существовала)'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Пользователь уже существует: {user.username}'
                        )
                    )
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Ошибка при создании {user_data["username"]}: {e}'
                    )
                )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✓ Создано {created_count} новых пользователей'))
        self.stdout.write('')
        self.stdout.write('Данные для входа:')
        self.stdout.write('  Логин: demo_observer_org / demo_admin / demo_hr_admin')
        self.stdout.write('  Пароль: demo123')
