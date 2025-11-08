"""
Django REST Framework Permission Classes для RBAC
"""
from rest_framework import permissions
from .rbac import check_permission


class RoleBasedPermission(permissions.BasePermission):
    """
    Базовый класс для проверки прав на основе ролей
    
    Использование в ViewSet:
        permission_classes = [IsAuthenticated, RoleBasedPermission]
        required_permission = 'view_staffing_table'
    
    Или создать специфичный класс:
        class CanViewStaffingTable(RoleBasedPermission):
            required_permission = 'view_staffing_table'
    """
    # Переопределяется в каждом view или в дочернем классе
    required_permission = None
    message = 'У вас нет прав для выполнения этого действия'
    
    def has_permission(self, request, view):
        """Проверка прав на уровне view"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Получить требуемое право
        permission = self.get_required_permission(request, view)
        if not permission:
            # Если право не указано - разрешаем (для совместимости)
            return True
        
        return check_permission(request.user, permission)
    
    def has_object_permission(self, request, view, obj):
        """Проверка прав на уровне объекта"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        permission = self.get_required_permission(request, view)
        if not permission:
            return True
        
        return check_permission(request.user, permission, obj)
    
    def get_required_permission(self, request, view):
        """
        Получить требуемое право
        
        Порядок поиска:
        1. required_permission класса permission
        2. required_permission view
        3. Автоматическое определение на основе action
        """
        # 1. Право указано в классе permission
        if self.required_permission:
            return self.required_permission
        
        # 2. Право указано в view
        if hasattr(view, 'required_permission'):
            return view.required_permission
        
        # 3. Право указано через permission_map для конкретного action
        if hasattr(view, 'permission_map') and hasattr(view, 'action'):
            action = view.action
            if action in view.permission_map:
                return view.permission_map[action]
        
        # 4. Автоматическое определение на основе action (для стандартных CRUD)
        if hasattr(view, 'action'):
            action = view.action
            model_name = view.queryset.model._meta.model_name if hasattr(view, 'queryset') else None
            
            if action == 'list':
                return f'view_{model_name}'
            elif action == 'retrieve':
                return f'view_{model_name}_details'
            elif action == 'create':
                return f'create_{model_name}'
            elif action in ['update', 'partial_update']:
                return f'edit_{model_name}'
            elif action == 'destroy':
                return f'delete_{model_name}'
        
        return None


# Специфичные permission classes для частых операций

class CanViewStaffingTable(RoleBasedPermission):
    """Право на просмотр штатного расписания"""
    required_permission = 'view_staffing_table'


class CanManageStaffingTable(RoleBasedPermission):
    """Право на управление штатным расписанием"""
    required_permission = 'manage_staffing_table'


class CanViewVacancies(RoleBasedPermission):
    """Право на просмотр вакансий"""
    required_permission = 'view_vacancies'


class CanCreateVacancy(RoleBasedPermission):
    """Право на создание вакансии"""
    required_permission = 'create_vacancy'


class CanEditVacancy(RoleBasedPermission):
    """Право на редактирование вакансии"""
    required_permission = 'edit_vacancy'


class CanCloseVacancy(RoleBasedPermission):
    """Право на закрытие вакансии"""
    required_permission = 'close_vacancy'


class ReadOnlyPermission(permissions.BasePermission):
    """
    Разрешает только безопасные методы (GET, HEAD, OPTIONS)
    
    Полезно для ролей-наблюдателей (ROLE_1, ROLE_2)
    """
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
    
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS


class IsRoleAdmin(permissions.BasePermission):
    """Проверка что пользователь имеет роль администратора (ROLE_4)"""
    message = 'Только администраторы могут выполнять это действие'
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if hasattr(request.user, 'role_info'):
            return request.user.role_info.role == 'ROLE_4'
        
        return False


class IsRoleHRAdmin(permissions.BasePermission):
    """Проверка что пользователь - кадровик (ROLE_5)"""
    message = 'Только кадровые администраторы могут выполнять это действие'
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if hasattr(request.user, 'role_info'):
            return request.user.role_info.role in ['ROLE_4', 'ROLE_5']
        
        return False
