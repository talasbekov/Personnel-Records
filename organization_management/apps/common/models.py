"""
Модели для системы ролей и прав доступа
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class UserRole(models.Model):
    """
    Модель для хранения ролевой информации пользователя
    
    Роли системы:
    - ROLE_1: Наблюдатель организации
    - ROLE_2: Наблюдатель департамента
    - ROLE_3: Начальник управления
    - ROLE_4: Системный администратор
    - ROLE_5: Кадровый администратор подразделения
    - ROLE_6: Начальник отдела
    """
    
    class RoleType(models.TextChoices):
        OBSERVER_ORG = 'ROLE_1', 'Наблюдатель организации'
        OBSERVER_DEPT = 'ROLE_2', 'Наблюдатель департамента'
        HEAD_DIRECTORATE = 'ROLE_3', 'Начальник управления'
        SYS_ADMIN = 'ROLE_4', 'Системный администратор'
        HR_ADMIN = 'ROLE_5', 'Кадровый администратор подразделения'
        HEAD_DIVISION = 'ROLE_6', 'Начальник отдела'
        HEAD_DEPARTMENT = 'ROLE_7', 'Начальник департамента'
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='role_info',
        verbose_name='Пользователь'
    )
    role = models.CharField(
        max_length=10, 
        choices=RoleType.choices,
        verbose_name='Роль'
    )
    
    # Область видимости (для ролей 2, 3, 5, 6)
    # Для гибкости используем один ForeignKey с разными related_name
    scope_division = models.ForeignKey(
        'divisions.Division',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='scoped_users',
        verbose_name='Подразделение (область видимости)',
        help_text='Департамент/Управление/Отдел в зависимости от роли'
    )
    
    # Для отслеживания откомандирования
    is_seconded = models.BooleanField(
        default=False,
        verbose_name='Откомандирован'
    )
    seconded_to = models.ForeignKey(
        'divisions.Division',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='seconded_users',
        verbose_name='Откомандирован в'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        db_table = 'user_roles'
        verbose_name = 'Роль пользователя'
        verbose_name_plural = 'Роли пользователей'
        ordering = ['user__username']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    def clean(self):
        """Валидация модели"""
        super().clean()

        # Роли 2, 3, 5, 6, 7 требуют наличия подразделения
        # (либо через scope_division, либо через Employee)
        roles_requiring_scope = [
            self.RoleType.OBSERVER_DEPT,
            self.RoleType.HEAD_DIRECTORATE,
            self.RoleType.HR_ADMIN,
            self.RoleType.HEAD_DIVISION,
            self.RoleType.HEAD_DEPARTMENT
        ]

        if self.role in roles_requiring_scope:
            # Проверяем, что можем определить подразделение
            division = self.get_user_division()
            if not division:
                raise ValidationError({
                    'scope_division': (
                        f'Для роли {self.get_role_display()} необходимо либо указать '
                        f'область видимости вручную, либо привязать пользователя к Employee с StaffUnit'
                    )
                })

        # Роли 1 и 4 не должны иметь область видимости
        roles_without_scope = [
            self.RoleType.OBSERVER_ORG,
            self.RoleType.SYS_ADMIN
        ]

        if self.role in roles_without_scope and self.scope_division:
            raise ValidationError({
                'scope_division': f'Для роли {self.get_role_display()} не должна быть указана область видимости'
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def department(self):
        """Возвращает департамент в зависимости от роли"""
        division = self.effective_scope_division
        if not division:
            return None

        if self.role == self.RoleType.OBSERVER_DEPT:
            # Для Роль-2 effective_scope_division это и есть департамент
            return division if division.level == 0 else None

        # Для остальных ролей ищем департамент вверх по иерархии
        return division.get_department()
    
    def get_user_division(self):
        """
        Автоматически определяет подразделение пользователя.

        Логика:
        1. Если пользователь откомандирован - возвращает seconded_to
        2. Если указан scope_division вручную - возвращает его (ВЫСОКИЙ ПРИОРИТЕТ)
        3. Если у пользователя есть Employee и StaffUnit - возвращает division из StaffUnit (автоматически)
        4. Иначе возвращает None

        Returns:
            Division или None
        """
        # Приоритет 1: Откомандирование
        if self.is_seconded and self.seconded_to:
            return self.seconded_to

        # Приоритет 2: Вручную указанное подразделение (переопределяет автоматическое)
        if self.scope_division:
            return self.scope_division

        # Приоритет 3: Автоматическое определение через Employee → StaffUnit → Division
        try:
            # User → Employee → StaffUnit → Division
            if hasattr(self.user, 'employee'):
                employee = self.user.employee
                if hasattr(employee, 'staff_unit') and employee.staff_unit:
                    return employee.staff_unit.division
        except Exception:
            pass

        return None

    @property
    def effective_scope_division(self):
        """
        Возвращает эффективную область видимости с учётом автоматического определения.
        Использовать это свойство вместо прямого обращения к scope_division.
        """
        return self.get_user_division()

    @property
    def can_edit_statuses(self):
        """Проверка права на редактирование статусов с учётом откомандирования"""
        if self.role == self.RoleType.SYS_ADMIN:
            return True

        if self.role in [self.RoleType.HEAD_DIRECTORATE, self.RoleType.HEAD_DIVISION, self.RoleType.HEAD_DEPARTMENT]:
            # Если откомандирован - не может редактировать статусы
            return not self.is_seconded

        # Роль-5 (кадровик) не может редактировать статусы
        if self.role == self.RoleType.HR_ADMIN:
            return False

        return False
