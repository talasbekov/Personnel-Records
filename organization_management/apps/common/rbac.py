"""
RBAC Engine - движок для проверки прав доступа на основе ролей
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
    role = role_info.role
    
    # Роль-4 (Системный администратор) имеет все права
    if role == 'ROLE_4':
        return True
    
    # Проверка откомандирования для ролей 3 и 6
    if role in ['ROLE_3', 'ROLE_6'] and role_info.is_seconded:
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
    
    Args:
        role: код роли (ROLE_1, ROLE_2, и т.д.)
        permission: название права
    
    Returns:
        bool: True если роль имеет право
    """
    # Матрица прав на основе МАТРИЦА_ПРАВ.md
    # Охватывает: StaffUnit, Vacancy, Employee, EmployeeStatus, Secondment, Division

    ROLE_PERMISSIONS = {
        'ROLE_1': [
            # === Наблюдатель организации - только просмотр ВСЕЙ организации ===
            # Штатное расписание и вакансии
            'view_staffing_table', 'view_staffing_table_all', 'view_position_quota',
            'view_staffing_statistics', 'view_vacancies', 'view_vacancies_all',
            # Сотрудники
            'view_employees', 'view_employee_details', 'view_employee_card',
            'view_employee_contacts', 'view_employee_history',
            # Статусы
            'view_employee_statuses', 'view_employee_status_history', 'view_all_statuses',
            'view_status_report',
            # Прикомандирование
            'view_secondments', 'view_secondment_details', 'view_secondment_history',
            # Структура
            'view_organization', 'view_department', 'view_directorate', 'view_division',
            'view_division_tree',
            # Отчёты
            'view_reports', 'generate_report_organization', 'download_report',
        ],
        'ROLE_2': [
            # === Наблюдатель департамента - просмотр ДЕПАРТАМЕНТА ===
            # Штатное расписание и вакансии
            'view_staffing_table', 'view_staffing_table_division', 'view_position_quota',
            'view_vacancies', 'view_vacancies_division',
            # Сотрудники
            'view_employees', 'view_employee_details', 'view_employee_card',
            'view_employee_history',
            # Статусы
            'view_employee_statuses', 'view_employee_status_history',
            'view_department_statuses',
            # Прикомандирование
            'view_secondments', 'view_secondment_details',
            # Структура
            'view_department', 'view_directorate', 'view_division',
            # Отчёты
            'generate_report_department', 'view_reports', 'download_report',
        ],
        'ROLE_3': [
            # === Начальник управления - просмотр департамента, редактирование управления ===
            # Штатное расписание и вакансии (просмотр)
            'view_staffing_table', 'view_staffing_table_division', 'view_position_quota',
            'view_vacancies', 'view_vacancies_division',
            # Сотрудники (просмотр)
            'view_employees', 'view_employee_details', 'view_employee_card',
            # Статусы (редактирование в управлении!)
            'view_employee_statuses', 'change_status_in_directorate', 'change_employee_status',
            'schedule_status', 'bulk_change_status', 'view_vacation_calendar',
            # Прикомандирование (может откомандировать из управления)
            'view_secondments', 'second_from_directorate', 'create_secondment_request',
            'approve_to_directorate', 'return_seconded_employee',
            # Структура (может редактировать управление)
            'view_department', 'edit_own_directorate', 'create_division_in_directorate',
            # Отчёты
            'generate_report_directorate', 'view_reports', 'download_report',
        ],
        'ROLE_4': [
            # === Системный администратор - ВСЕ ПРАВА ===
            # Штатное расписание и вакансии
            'view_staffing_table', 'view_staffing_table_all', 'view_position_quota',
            'view_staffing_statistics', 'manage_staffing_table', 'create_staffing_position',
            'edit_staffing_position', 'delete_staffing_position', 'change_position_quota',
            'reserve_position', 'view_vacancies', 'create_vacancy', 'edit_vacancy',
            'close_vacancy', 'fill_vacancy', 'publish_vacancy', 'unpublish_vacancy',
            # Сотрудники
            'view_employees', 'view_employee_details', 'hire_employee', 'fire_employee',
            'edit_employee', 'edit_employee_personal_data', 'upload_employee_photo',
            'transfer_employee', 'assign_position', 'change_position',
            # Статусы
            'view_employee_statuses', 'change_employee_status', 'change_status_all',
            'schedule_status', 'bulk_change_status', 'view_all_statuses',
            # Прикомандирование
            'view_secondments', 'second_employee', 'approve_secondment_request',
            'reject_secondment_request', 'return_seconded_employee',
            # Структура
            'view_organization', 'create_department', 'edit_department', 'delete_department',
            'create_directorate', 'edit_directorate', 'create_division', 'edit_division',
            # Отчёты
            'generate_report', 'generate_report_organization', 'view_reports',
            'manage_report_templates',
            # Права и пользователи
            'view_users', 'create_user', 'edit_user', 'assign_role', 'manage_permissions',
            # Справочники
            'manage_dictionaries', 'create_dictionary_item', 'edit_dictionary_item',
            # Аудит
            'view_audit_log', 'view_audit_log_all', 'export_audit_log',
        ],
        'ROLE_5': [
            # === Кадровый администратор - управление кадрами в ПОДРАЗДЕЛЕНИИ ===
            # Штатное расписание и вакансии
            'view_staffing_table', 'view_staffing_table_division', 'manage_staffing_table_division',
            'create_staffing_position', 'edit_staffing_position', 'delete_staffing_position',
            'view_vacancies', 'view_vacancies_division', 'create_vacancy_division',
            'edit_vacancy', 'close_vacancy', 'fill_vacancy',
            # Сотрудники (может нанимать и редактировать в подразделении)
            'view_employees', 'view_employee_details', 'hire_employee_in_division',
            'edit_employee_in_division', 'edit_employee_personal_data',
            'upload_employee_photo', 'transfer_employee_in_division',
            'assign_position', 'assign_position_regular', 'assign_position_acting',
            # Статусы (НЕ МОЖЕТ изменять)
            'view_employee_statuses', 'view_employee_status_history',
            # Структура (ограниченное управление)
            'view_department', 'view_directorate', 'view_division',
            'create_division_in_directorate',
            # Отчёты (штатное расписание)
            'generate_report_division_staffing', 'view_reports', 'download_report',
            # Аудит
            'view_audit_log_own_division',
        ],
        'ROLE_6': [
            # === Начальник отдела - просмотр департамента, редактирование ОТДЕЛА ===
            # Штатное расписание и вакансии (просмотр)
            'view_staffing_table', 'view_staffing_table_division', 'view_position_quota',
            'view_vacancies', 'view_vacancies_division',
            # Сотрудники (просмотр)
            'view_employees', 'view_employee_details', 'view_employee_card',
            # Статусы (редактирование в отделе)
            'view_employee_statuses', 'change_status_in_division', 'change_employee_status',
            'schedule_status', 'view_vacation_calendar',
            # Прикомандирование (только просмотр)
            'view_secondments',
            # Структура (просмотр департамента)
            'view_department', 'view_directorate', 'view_division',
            # Отчёты
            'generate_report_division', 'view_reports', 'download_report',
        ],
    }
    
    # Нормализация названия права (убрать префикс приложения если есть)
    perm_name = permission.split('.')[-1] if '.' in permission else permission
    
    role_perms = ROLE_PERMISSIONS.get(role, [])
    
    # Прямое совпадение
    if perm_name in role_perms:
        return True
    
    # Частичное совпадение для гибкости (например 'view_' в 'view_staffing_table')
    for role_perm in role_perms:
        if perm_name in role_perm or role_perm in perm_name:
            return True
    
    return False


def is_in_scope(user: User, obj: Any, permission: str) -> bool:
    """
    Проверка что объект находится в области видимости пользователя
    
    Args:
        user: Django User
        obj: проверяемый объект
        permission: название права
    
    Returns:
        bool: True если объект в области видимости
    """
    role_info = user.role_info
    role = role_info.role
    
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
        department = role_info.scope_division
        if not department:
            return False
        return is_in_department(obj_division, department)
    
    # Роль-3: просмотр - департамент, редактирование - управление
    if role == 'ROLE_3':
        directorate = role_info.scope_division
        if not directorate:
            return False
        
        # Для просмотра достаточно быть в департаменте
        if permission.startswith('view_'):
            department = directorate.get_department() if hasattr(directorate, 'get_department') else directorate.parent
            return is_in_department(obj_division, department)
        
        # Для редактирования должно быть в управлении
        return is_in_directorate(obj_division, directorate)
    
    # Роль-5: подразделение (может быть департамент, управление или отдел)
    if role == 'ROLE_5':
        scope = role_info.scope_division
        if not scope:
            return False
        return is_in_subtree(obj_division, scope)
    
    # Роль-6: просмотр - департамент, редактирование - отдел
    if role == 'ROLE_6':
        division = role_info.scope_division
        if not division:
            return False
        
        # Для просмотра достаточно быть в департаменте
        if permission.startswith('view_'):
            department = division.get_department() if hasattr(division, 'get_department') else division.get_ancestors().filter(level=0).first()
            return is_in_department(obj_division, department)
        
        # Для редактирования должно быть в отделе
        return obj_division == division or obj_division.is_descendant_of(division)
    
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
    role = role_info.role

    # Роли с полным доступом
    if role in ['ROLE_1', 'ROLE_4'] or user.is_superuser:
        return model_class.objects.all()

    # Определить поле для фильтрации в зависимости от модели
    model_name = model_class.__name__
    division_field = _get_division_field_for_model(model_name)

    if not division_field:
        return model_class.objects.none()

    scope = role_info.scope_division
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

    # Роль-3: департамент (весь) для просмотра
    if role == 'ROLE_3':
        # Найти департамент (родительское подразделение level=0)
        department = scope
        if hasattr(scope, 'get_ancestors'):
            ancestors = scope.get_ancestors()
            dept = ancestors.filter(level=0).first()
            if dept:
                department = dept

        if hasattr(department, 'get_descendants'):
            return list(department.get_descendants(include_self=True).values_list('id', flat=True))
        return [department.id]

    # Роль-5: подразделение и все дочерние
    if role == 'ROLE_5':
        if hasattr(scope, 'get_descendants'):
            return list(scope.get_descendants(include_self=True).values_list('id', flat=True))
        return [scope.id]

    # Роль-6: департамент для просмотра
    if role == 'ROLE_6':
        # Найти департамент
        department = scope
        if hasattr(scope, 'get_ancestors'):
            ancestors = scope.get_ancestors()
            dept = ancestors.filter(level=0).first()
            if dept:
                department = dept

        if hasattr(department, 'get_descendants'):
            return list(department.get_descendants(include_self=True).values_list('id', flat=True))
        return [department.id]

    return []
