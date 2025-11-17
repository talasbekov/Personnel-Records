"""
Модели для системы ролей и прав доступа
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.cache import cache


class Role(models.Model):
    """
    Модель для хранения ролей системы в БД.
    Позволяет создавать роли через админку без изменения кода.
    """
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Код роли',
        help_text='Уникальный код роли (например, ROLE_1, ROLE_2)'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название роли',
        help_text='Человекочитаемое название роли'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Подробное описание роли и её полномочий'
    )

    # Иерархия подразделений: 0=организация, 1=департамент, 2=управление, 3=отдел
    hierarchy_level = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Уровень иерархии',
        help_text='0=вся организация, 1=департамент, 2=управление, 3=отдел, null=не привязан к уровню',
        choices=[
            (None, 'Не привязан к уровню'),
            (0, 'Вся организация'),
            (1, 'Департамент'),
            (2, 'Управление'),
            (3, 'Отдел'),
        ]
    )

    requires_scope = models.BooleanField(
        default=True,
        verbose_name='Требует область видимости',
        help_text='Должна ли роль иметь привязку к подразделению'
    )

    can_edit_statuses = models.BooleanField(
        default=False,
        verbose_name='Может редактировать статусы',
        help_text='Может ли роль изменять статусы сотрудников'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
        help_text='Можно деактивировать роль без удаления'
    )

    sort_order = models.IntegerField(
        default=0,
        verbose_name='Порядок сортировки',
        help_text='Для упорядочивания ролей в списках'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')

    class Meta:
        db_table = 'roles'
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_permissions(self):
        """Получить все права роли с кешированием"""
        cache_key = f'role_permissions:{self.id}'
        permissions = cache.get(cache_key)

        if permissions is None:
            permissions = list(
                self.role_permissions.filter(is_active=True)
                .select_related('permission')
                .values_list('permission__code', flat=True)
            )
            # Кешируем на 1 час
            cache.set(cache_key, permissions, 3600)

        return permissions

    def invalidate_cache(self):
        """Инвалидировать кеш прав роли"""
        cache_key = f'role_permissions:{self.id}'
        cache.delete(cache_key)


class Permission(models.Model):
    """
    Модель для хранения прав доступа системы.
    Позволяет создавать новые права через админку.
    """

    class Category(models.TextChoices):
        STAFFING = 'staffing', 'Штатное расписание'
        VACANCY = 'vacancy', 'Вакансии'
        EMPLOYEE = 'employee', 'Сотрудники'
        STATUS = 'status', 'Статусы'
        SECONDMENT = 'secondment', 'Прикомандирование'
        STRUCTURE = 'structure', 'Структура организации'
        REPORT = 'report', 'Отчёты'
        ADMIN = 'admin', 'Администрирование'
        AUDIT = 'audit', 'Аудит'

    code = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Код права',
        help_text='Уникальный код права (например, view_staffing_table)'
    )
    name = models.CharField(
        max_length=200,
        verbose_name='Название',
        help_text='Человекочитаемое название права'
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        verbose_name='Категория',
        help_text='Категория для группировки прав'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
        help_text='Подробное описание права'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно',
        help_text='Можно деактивировать право без удаления'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        db_table = 'permissions'
        verbose_name = 'Право доступа'
        verbose_name_plural = 'Права доступа'
        ordering = ['category', 'code']

    def __str__(self):
        return f"{self.code} ({self.get_category_display()})"


class RolePermission(models.Model):
    """
    Связующая таблица между ролями и правами (Many-to-Many).
    Позволяет назначать права ролям через админку.
    """

    class ScopeType(models.TextChoices):
        ORGANIZATION = 'organization', 'Вся организация'
        DEPARTMENT = 'department', 'Департамент'
        OWN_DIVISION = 'own_division', 'Собственное подразделение'
        CUSTOM = 'custom', 'Пользовательская область'

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions',
        verbose_name='Роль'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='permission_roles',
        verbose_name='Право'
    )

    scope_type = models.CharField(
        max_length=20,
        choices=ScopeType.choices,
        default=ScopeType.OWN_DIVISION,
        verbose_name='Тип области видимости',
        help_text='На каком уровне применяется право'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно',
        help_text='Можно временно отключить право у роли'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        db_table = 'role_permissions'
        verbose_name = 'Право роли'
        verbose_name_plural = 'Права ролей'
        unique_together = [['role', 'permission']]
        ordering = ['role__code', 'permission__category', 'permission__code']

    def __str__(self):
        return f"{self.role.code} -> {self.permission.code}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Инвалидируем кеш роли при изменении её прав
        self.role.invalidate_cache()

    def delete(self, *args, **kwargs):
        role = self.role
        super().delete(*args, **kwargs)
        # Инвалидируем кеш роли при удалении права
        role.invalidate_cache()


class UserRole(models.Model):
    """
    Модель для хранения ролевой информации пользователя.

    Роль определяется через связь с моделью Role (таблица БД).
    Все права и настройки роли управляются через Django админку.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='role_info',
        verbose_name='Пользователь'
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='users',
        verbose_name='Роль',
        help_text='Роль пользователя из системы RBAC'
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

        # Проверяем требование области видимости на основе настроек роли
        if self.role.requires_scope:
            # Проверяем, что можем определить подразделение
            division = self.get_user_division()
            if not division:
                raise ValidationError({
                    'scope_division': (
                        f'Для роли {self.role.name} необходимо либо указать '
                        f'область видимости вручную, либо привязать пользователя к Employee с StaffUnit'
                    )
                })

        # Роли без требования scope не должны иметь scope_division
        if not self.role.requires_scope and self.scope_division:
            raise ValidationError({
                'scope_division': f'Для роли {self.role.name} не должна быть указана область видимости'
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

        # Если роль на уровне департамента (level=1) - возвращаем как есть
        if self.role.hierarchy_level == 1:
            return division if division.level == 1 else None

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
        if self.role.can_edit_statuses:
            # Если откомандирован - не может редактировать статусы
            return not self.is_seconded
        return False

    def get_role_code(self):
        """
        Получить код роли.
        Возвращает строку вида 'ROLE_1', 'ROLE_2' и т.д.
        """
        return self.role.code

    def get_role_name(self):
        """Получить название роли"""
        return self.role.name

    def get_role_display(self):
        """Получить название роли (для совместимости с Django)"""
        return self.role.name

    def get_role_hierarchy_level(self):
        """Получить уровень иерархии роли"""
        return self.role.hierarchy_level

    def requires_scope(self):
        """Проверка, требует ли роль область видимости"""
        return self.role.requires_scope
