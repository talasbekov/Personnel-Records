"""
Кастомные JWT serializers для включения ролей и прав в токен
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Кастомный serializer для добавления информации о роли в JWT токен
    """
    
    @classmethod
    def get_token(cls, user):
        """Добавляем дополнительные claims в токен"""
        token = super().get_token(user)
        
        # Базовая информация о пользователе
        token['username'] = user.username
        token['email'] = user.email
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser



        # Информация о роли
        if hasattr(user, 'role_info'):
            role_info = user.role_info

            # Роль
            token['role'] = role_info.get_role_code()
            token['role_name'] = role_info.get_role_display()

            # Область видимости (автоматически определяется)
            effective_division = role_info.effective_scope_division
            if effective_division:
                token['scope_division_id'] = effective_division.id
                token['scope_division_name'] = effective_division.name
                token['scope_division_level'] = effective_division.level

                # Для удобства добавляем тип подразделения
                if effective_division.level == 0:
                    token['scope_type'] = 'department'
                elif effective_division.level == 1:
                    token['scope_type'] = 'directorate'
                else:
                    token['scope_type'] = 'division'

                # Добавляем информацию об источнике подразделения
                if role_info.is_seconded and role_info.seconded_to:
                    token['scope_source'] = 'secondment'
                elif hasattr(user, 'employee'):
                    try:
                        if hasattr(user.employee, 'staff_unit') and user.employee.staff_unit:
                            token['scope_source'] = 'auto'
                    except:
                        pass
                if 'scope_source' not in token and role_info.scope_division:
                    token['scope_source'] = 'manual'
            else:
                token['scope_division_id'] = None
                token['scope_type'] = 'all'  # Вся организация
                token['scope_source'] = 'none'
            
            # Статус откомандирования
            token['is_seconded'] = role_info.is_seconded
            if role_info.is_seconded and role_info.seconded_to:
                token['seconded_to_id'] = role_info.seconded_to.id
                token['seconded_to_name'] = role_info.seconded_to.name
            
            # Специальные флаги для быстрой проверки на фронтенде
            token['can_edit_statuses'] = role_info.can_edit_statuses
            token['is_admin'] = role_info.get_role_code() == 'ROLE_4'
            token['is_hr_admin'] = role_info.get_role_code() == 'ROLE_5'
            token['is_observer'] = role_info.get_role_code() in ['ROLE_1', 'ROLE_2']
            token['is_manager'] = role_info.get_role_code() in ['ROLE_3', 'ROLE_6']
        
        else:
            # У пользователя нет роли - возможно это суперпользователь
            token['role'] = None
            token['role_name'] = 'Суперпользователь' if user.is_superuser else 'Нет роли'
            token['scope_division_id'] = None
            token['scope_type'] = 'all' if user.is_superuser else 'none'
            token['is_seconded'] = False
            token['can_edit_statuses'] = user.is_superuser
            token['is_admin'] = user.is_superuser
            token['is_hr_admin'] = False
            token['is_observer'] = False
            token['is_manager'] = False
        
        # Информация о сотруднике (если есть)
        if hasattr(user, 'employee'):
            employee = user.employee
            token['employee_id'] = employee.id
            token['employee_full_name'] = f'{employee.last_name} {employee.first_name} {employee.middle_name}'
            token['employee_personnel_number'] = employee.personnel_number
        
        return token
    
    def validate(self, attrs):
        """Валидация и добавление дополнительной информации в response"""
        data = super().validate(attrs)
        
        # Добавляем информацию о пользователе в response
        user = self.user
        
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
        }
        
        # Добавляем информацию о роли
        if hasattr(user, 'role_info'):
            role_info = user.role_info
            data['user']['role'] = {
                'code': role_info.get_role_code(),
                'name': role_info.get_role_display(),
                'is_seconded': role_info.is_seconded,
                'can_edit_statuses': role_info.can_edit_statuses,
            }

            effective_division = role_info.effective_scope_division
            if effective_division:
                # Определяем источник подразделения
                scope_source = 'manual'
                if role_info.is_seconded and role_info.seconded_to:
                    scope_source = 'secondment'
                elif hasattr(user, 'employee'):
                    try:
                        if hasattr(user.employee, 'staff_unit') and user.employee.staff_unit:
                            scope_source = 'auto'
                    except:
                        pass

                data['user']['role']['scope'] = {
                    'id': effective_division.id,
                    'name': effective_division.name,
                    'level': effective_division.level,
                    'source': scope_source,
                }
        
        return data


def get_tokens_for_user(user):
    """
    Вспомогательная функция для генерации токенов для пользователя
    
    Args:
        user: Django User объект
    
    Returns:
        dict: {'refresh': '...', 'access': '...'}
    """
    refresh = RefreshToken.for_user(user)
    
    # Добавляем кастомные claims через наш serializer
    serializer = CustomTokenObtainPairSerializer()
    token = serializer.get_token(user)
    
    return {
        'refresh': str(token),
        'access': str(token.access_token),
    }
