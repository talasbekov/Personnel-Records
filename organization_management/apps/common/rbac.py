"""
RBAC Engine - движок для проверки прав доступа на основе ролей

Система полностью основана на БД:
- Роли хранятся в таблице Role
- Права хранятся в таблице Permission
- Связи роль-право в таблице RolePermission

Все настройки управляются через Django админку без изменения кода.
"""
from typing import Optional, Any
from django.contrib.auth.models import User


def check_permission(user: User, permission: str, obj: Any = None) -> bool:
    """
    Главная функция проверки прав доступа
    
    Args:
        user: Django User объект
        permission: строка вида 'app.permission_name' или просто 'permission_name'
        obj: объект для проверки (Employee, Division, StaffUnit и т.д.)
    
    Returns:
        bool: True если доступ разрешен, False если запрещен
    
    Examples:
        >>> check_permission(user, 'view_staffing_table')
        >>> check_permission(user, 'edit_vacancy', vacancy_obj)
    """
    # Проверка что пользователь аутентифицирован
    if not user or not user.is_authenticated:
        return False
    
    # Суперпользователь имеет все права
    if user.is_superuser:
        return True
    
    # Проверка наличия роли
    if not hasattr(user, 'role_info'):
        return False
    
    role_info = user.role_info

    # Получаем код роли (работает для обеих систем)
    role = role_info.get_role_code()

    # Роль-4 (Системный администратор) имеет все права
    if role == 'ROLE_4':
        return True

    # Проверка откомандирования для ролей 3, 6, 7
    if role in ['ROLE_3', 'ROLE_6', 'ROLE_7'] and role_info.is_seconded:
        # Откомандированные начальники не могут редактировать статусы и данные
        restricted_permissions = [
            'change_status', 'edit_status', 'change_employee_status',
            'edit_employee', 'edit_division', 'edit_directorate'
        ]
        if any(perm in permission for perm in restricted_permissions):
            return False
    
    # Проверка конкретного права для роли
    if not has_role_permission(role, permission):
        return False
    
    # Проверка области видимости если передан объект
    if obj:
        return is_in_scope(user, obj, permission)
    
    return True


def has_role_permission(role: str, permission: str) -> bool:
    """
    Проверка что роль имеет данное право (базовая проверка без учёта области видимости)

    Читает права из БД с кешированием для производительности.

    Args:
        role: код роли (ROLE_1, ROLE_2, и т.д.)
        permission: название права

    Returns:
        bool: True если роль имеет право

    Raises:
        Exception: Если роль не найдена в БД
    """
    # Нормализация названия права (убрать префикс приложения если есть)
    perm_name = permission.split('.')[-1] if '.' in permission else permission

    try:
        from .models import Role

        # Получаем роль из БД
        role_obj = Role.objects.filter(code=role, is_active=True).first()

        if not role_obj:
            # Роль не найдена - по умолчанию запрещаем доступ
            return False

        # Получаем права роли (с кешированием)
        role_permissions = role_obj.get_permissions()

        # Прямое совпадение
        if perm_name in role_permissions:
            return True

        # Частичное совпадение для гибкости
        for role_perm in role_permissions:
            if perm_name in role_perm or role_perm in perm_name:
                return True

        return False

    except Exception as e:
        # Логируем ошибку и запрещаем доступ
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error checking permission {permission} for role {role}: {e}")
        return False


def is_in_scope(user: User, obj: Any, permission: str) -> bool:
    """
    Проверка что объект находится в области видимости пользователя

    Работает с обеими системами RBAC (старой и новой).

    Args:
        user: Django User
        obj: проверяемый объект
        permission: название права

    Returns:
        bool: True если объект в области видимости
    """
    role_info = user.role_info

    # Получаем код роли (работает для обеих систем)
    role = role_info.get_role_code()
    
    # Получить подразделение объекта
    obj_division = get_object_division(obj)
    
    if not obj_division:
        # Если не удалось определить подразделение - запрещаем
        return False
    
    # Роль-1: вся организация
    if role == 'ROLE_1':
        return True
    
    # Роль-4: вся организация
    if role == 'ROLE_4':
        return True
    
    # Роль-2: только департамент
    if role == 'ROLE_2':
        department = role_info.effective_scope_division
        if not department:
            return False
        return is_in_department(obj_division, department)
    
    # Роль-3: просмотр и редактирование - только СВОЕ управление и дочерние отделы
    # НЕ весь департамент!
    if role == 'ROLE_3':
        directorate = role_info.effective_scope_division
        if not directorate:
            return False

        # Для просмотра - только управление и его дочерние
        if permission.startswith('view_'):
            return is_in_directorate(obj_division, directorate)

        # Для редактирования - также только управление
        return is_in_directorate(obj_division, directorate)
    
    # Роль-5: подразделение (может быть департамент, управление или отдел)
    if role == 'ROLE_5':
        scope = role_info.effective_scope_division
        if not scope:
            return False
        return is_in_subtree(obj_division, scope)
    
    # Роль-6: просмотр и редактирование - только СВОЙ отдел и дочерние подразделения
    # НЕ весь департамент!
    if role == 'ROLE_6':
        division = role_info.effective_scope_division
        if not division:
            return False

        # Для просмотра - только отдел и его дочерние
        if permission.startswith('view_'):
            return obj_division == division or (hasattr(obj_division, 'is_descendant_of') and obj_division.is_descendant_of(division))

        # Для редактирования - также только отдел
        return obj_division == division or (hasattr(obj_division, 'is_descendant_of') and obj_division.is_descendant_of(division))

    # Роль-7: весь департамент (просмотр и редактирование)
    if role == 'ROLE_7':
        department = role_info.effective_scope_division
        if not department:
            return False
        return is_in_department(obj_division, department)

    return False


def get_object_division(obj: Any):
    """
    Получить подразделение объекта для ЛЮБОЙ модели системы

    Поддерживаемые модели:
    - Division: само подразделение
    - StaffUnit: через поле division
    - Vacancy: через staff_unit.division
    - Employee: через staff_unit (текущая штатная единица)
    - EmployeeStatus: через employee.staff_unit.division
    - Secondment: через from_division или to_division
    - Report: через division (если есть)

    Args:
        obj: объект любой модели системы

    Returns:
        Division или None
    """
    if not obj:
        return None

    model_name = obj.__class__.__name__

    # 1. Division - сам объект
    if model_name == 'Division':
        return obj

    # 2. StaffUnit - прямое поле division
    if hasattr(obj, 'division') and obj.division:
        return obj.division

    # 3. Vacancy - через staff_unit
    if model_name == 'Vacancy':
        if hasattr(obj, 'staff_unit') and obj.staff_unit:
            return obj.staff_unit.division if hasattr(obj.staff_unit, 'division') else None

    # 4. Employee - через текущую штатную единицу
    if model_name == 'Employee':
        # Используем staff_unit (OneToOne)
        if hasattr(obj, 'staff_unit') and obj.staff_unit:
            return obj.staff_unit.division
        # Fallback: через staffunit_set
        if hasattr(obj, 'staffunit_set'):
            staff_unit = obj.staffunit_set.first()
            return staff_unit.division if staff_unit and hasattr(staff_unit, 'division') else None

    # 5. EmployeeStatus - через employee
    if model_name == 'EmployeeStatus':
        if hasattr(obj, 'employee') and obj.employee:
            return get_object_division(obj.employee)
        # Альтернативно через related_division (если есть)
        if hasattr(obj, 'related_division') and obj.related_division:
            return obj.related_division

    # 6. Secondment - зависит от контекста
    if model_name == 'Secondment':
        # Для откомандирования используем from_division
        if hasattr(obj, 'from_division') and obj.from_division:
            return obj.from_division
        # Для прикомандирования используем to_division
        if hasattr(obj, 'to_division') and obj.to_division:
            return obj.to_division

    # 7. EmployeeTransferHistory - через from_division или to_division
    if model_name == 'EmployeeTransferHistory':
        if hasattr(obj, 'to_division') and obj.to_division:
            return obj.to_division
        if hasattr(obj, 'from_division') and obj.from_division:
            return obj.from_division

    # 8. StatusDocument - через status.employee
    if model_name == 'StatusDocument':
        if hasattr(obj, 'status') and obj.status:
            return get_object_division(obj.status)

    # 9. StatusChangeHistory - через status
    if model_name == 'StatusChangeHistory':
        if hasattr(obj, 'status') and obj.status:
            return get_object_division(obj.status)

    # 10. Report - может иметь division
    if model_name in ['Report', 'GeneratedReport']:
        if hasattr(obj, 'division') and obj.division:
            return obj.division

    # Универсальный fallback: если есть поле division
    if hasattr(obj, 'division') and obj.division:
        return obj.division

    # Если ничего не нашли
    return None


def is_in_department(division, department) -> bool:
    """Проверка что подразделение входит в департамент"""
    if not division or not department:
        return False
    
    # Если само подразделение - департамент
    if division == department:
        return True
    
    # Проверка через MPTT
    if hasattr(division, 'is_descendant_of'):
        return division.is_descendant_of(department) or division == department
    
    # Проверка через get_ancestors
    if hasattr(division, 'get_ancestors'):
        return department in division.get_ancestors(include_self=True)
    
    return False


def is_in_directorate(division, directorate) -> bool:
    """Проверка что подразделение входит в управление"""
    if not division or not directorate:
        return False
    
    if division == directorate:
        return True
    
    if hasattr(division, 'is_descendant_of'):
        return division.is_descendant_of(directorate)
    
    if hasattr(division, 'get_ancestors'):
        return directorate in division.get_ancestors(include_self=True)
    
    return False


def is_in_subtree(division, scope) -> bool:
    """Проверка что подразделение входит в поддерево scope"""
    if not division or not scope:
        return False
    
    if division == scope:
        return True
    
    if hasattr(division, 'is_descendant_of'):
        return division.is_descendant_of(scope)
    
    if hasattr(division, 'get_ancestors'):
        return scope in division.get_ancestors(include_self=True)
    
    return False


def get_user_scope_queryset(user: User, model_class):
    """
    Получить queryset с учётом области видимости пользователя для ЛЮБОЙ модели

    Работает с обеими системами RBAC (старой и новой).

    Поддерживаемые модели:
    - Division, StaffUnit, Vacancy (прямое поле division)
    - Employee (через staff_unit__division)
    - EmployeeStatus (через employee__staff_unit__division)
    - Secondment (через from_division или to_division)
    - Report (через division)

    Args:
        user: Django User
        model_class: класс модели

    Returns:
        QuerySet с фильтрацией по области видимости
    """
    if not hasattr(user, 'role_info'):
        return model_class.objects.none()

    role_info = user.role_info

    # Получаем код роли (работает для обеих систем)
    role = role_info.get_role_code()

    # Роли с полным доступом ко всей организации
    if role in ['ROLE_1', 'ROLE_4'] or user.is_superuser:
        return model_class.objects.all()

    # Определить поле для фильтрации в зависимости от модели
    model_name = model_class.__name__
    division_field = _get_division_field_for_model(model_name)

    if not division_field:
        return model_class.objects.none()

    scope = role_info.effective_scope_division
    if not scope:
        return model_class.objects.none()

    # Получить список ID подразделений в области видимости
    division_ids = _get_scope_division_ids(role, scope)

    if not division_ids:
        return model_class.objects.none()

    # Применить фильтр
    return model_class.objects.filter(**{f'{division_field}__id__in': division_ids})


def _get_division_field_for_model(model_name: str) -> str:
    """
    Определить поле для фильтрации по подразделению для конкретной модели

    Args:
        model_name: название модели

    Returns:
        строка с путём к полю division
    """
    # Маппинг моделей на пути к полю division
    DIVISION_FIELD_MAP = {
        # Прямое поле division
        'Division': 'id',  # для Division фильтруем по id
        'StaffUnit': 'division',
        'Vacancy': 'staff_unit__division',

        # Через employee
        'Employee': 'staff_unit__division',
        'EmployeeTransferHistory': 'employee__staff_unit__division',

        # Через employee.staff_unit.division
        'EmployeeStatus': 'employee__staff_unit__division',
        'StatusDocument': 'status__employee__staff_unit__division',
        'StatusChangeHistory': 'status__employee__staff_unit__division',

        # Secondment - используем from_division
        'Secondment': 'from_division',

        # Report
        'Report': 'division',
        'GeneratedReport': 'division',
    }

    return DIVISION_FIELD_MAP.get(model_name, 'division')


def _get_scope_division_ids(role: str, scope) -> list:
    """
    Получить список ID подразделений в области видимости роли

    Args:
        role: код роли (ROLE_1, ROLE_2, и т.д.)
        scope: Division объект (scope_division из UserRole)

    Returns:
        список ID подразделений
    """
    if not scope:
        return []

    # Роль-2: департамент и все дочерние
    if role == 'ROLE_2':
        if hasattr(scope, 'get_descendants'):
            return list(scope.get_descendants(include_self=True).values_list('id', flat=True))
        return [scope.id]

    # Роль-3: весь департамент (родитель управления и все его потомки)
    if role == 'ROLE_3':
        # Если scope уже на уровне департамента (level=1), возвращаем его и потомков
        if scope.level == 1:
            if hasattr(scope, 'get_descendants'):
                return list(scope.get_descendants(include_self=True).values_list('id', flat=True))
            return [scope.id]

        # Если scope на уровне управления (level=2), поднимаемся к департаменту
        if scope.level == 2 and scope.parent:
            department = scope.parent
            if hasattr(department, 'get_descendants'):
                return list(department.get_descendants(include_self=True).values_list('id', flat=True))
            return [department.id]

        # Для других уровней возвращаем scope и его потомков
        if hasattr(scope, 'get_descendants'):
            return list(scope.get_descendants(include_self=True).values_list('id', flat=True))
        return [scope.id]

    # Роль-5: подразделение и все дочерние
    if role == 'ROLE_5':
        if hasattr(scope, 'get_descendants'):
            return list(scope.get_descendants(include_self=True).values_list('id', flat=True))
        return [scope.id]

    # Роль-6: весь департамент (поднимаемся к департаменту через родителей)
    if role == 'ROLE_6':
        # Отдел обычно на уровне 3, управление на уровне 2, департамент на уровне 1
        # Поднимаемся к департаменту
        current = scope
        # Ищем департамент (обычно level=1)
        while current.parent and current.level > 1:
            current = current.parent

        # Теперь current должен быть департаментом
        if hasattr(current, 'get_descendants'):
            return list(current.get_descendants(include_self=True).values_list('id', flat=True))
        return [current.id]

    # Роль-7: весь департамент (аналогично ROLE_2)
    if role == 'ROLE_7':
        if hasattr(scope, 'get_descendants'):
            return list(scope.get_descendants(include_self=True).values_list('id', flat=True))
        return [scope.id]

    return []
