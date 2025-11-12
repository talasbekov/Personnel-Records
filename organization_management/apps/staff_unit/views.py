from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction

from organization_management.apps.staff_unit.models import Vacancy, StaffUnit
from organization_management.apps.staff_unit.serializers import (
    VacancySerializer,
    StaffUnitSerializer,
    StaffUnitBulkUpdateSerializer,
    StaffUnitDetailedSerializer,
)
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.dictionaries.api.serializers import PositionSerializer
from organization_management.apps.common.drf_permissions import (
    RoleBasedPermission,
    CanViewVacancies,
    CanCreateVacancy,
    CanEditVacancy,
    CanViewStaffingTable,
    CanManageStaffingTable
)
from organization_management.apps.common.rbac import get_user_scope_queryset, check_permission
from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.models import Employee
from organization_management.apps.statuses.models import EmployeeStatus


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()


class VacancyViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления вакансиями с проверкой прав на основе ролей
    """
    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer

    # Маппинг actions на требуемые права
    permission_map = {
        'list': 'view_vacancies',
        'retrieve': 'view_vacancies',
        'create': 'create_vacancy',
        'update': 'edit_vacancy',
        'partial_update': 'edit_vacancy',
        'destroy': 'close_vacancy',
    }

    def get_permissions(self):
        """Динамическое определение permissions на основе action"""
        if self.action in ['create']:
            return [permissions.IsAuthenticated(), CanCreateVacancy()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), CanEditVacancy()]
        else:
            return [permissions.IsAuthenticated(), CanViewVacancies()]

    def get_queryset(self):
        """Фильтрация queryset по области видимости пользователя"""
        user = self.request.user

        # Суперпользователь видит всё
        if user.is_superuser:
            return Vacancy.objects.all()

        # Используем RBAC engine для фильтрации
        return get_user_scope_queryset(user, Vacancy)

    def perform_create(self, serializer):
        """
        Проверка прав при создании вакансии
        Вакансия будет связана с StaffUnit, проверяем scope через него
        """
        user = self.request.user

        # Базовая проверка прав на создание вакансий
        if not user.is_superuser and hasattr(user, 'role_info'):
            if not check_permission(user, 'create_vacancy'):
                raise PermissionDenied(
                    "У вас нет прав для создания вакансий"
                )

        serializer.save()

    def perform_update(self, serializer):
        """
        Проверка прав при обновлении вакансии
        """
        user = self.request.user
        instance = self.get_object()

        if not user.is_superuser:
            if not check_permission(user, 'edit_vacancy', instance):
                raise PermissionDenied(
                    "У вас нет прав для редактирования этой вакансии"
                )

        serializer.save()

    def perform_destroy(self, instance):
        """
        Проверка прав при закрытии/удалении вакансии
        """
        user = self.request.user

        if not user.is_superuser:
            if not check_permission(user, 'close_vacancy', instance):
                raise PermissionDenied(
                    "У вас нет прав для закрытия этой вакансии"
                )

        # Вместо удаления - закрываем вакансию
        instance.status = Vacancy.VacancyStatus.CLOSED
        instance.save()


class StaffUnitViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления штатным расписанием с проверкой прав на основе ролей
    """
    queryset = StaffUnit.objects.all()
    serializer_class = StaffUnitSerializer

    # Маппинг actions на требуемые права
    permission_map = {
        'list': 'view_staffing_table',
        'retrieve': 'view_staffing_table',
        'create': 'create_staffing_position',
        'update': 'edit_staffing_position',
        'partial_update': 'edit_staffing_position',
        'destroy': 'delete_staffing_position',
    }

    def get_permissions(self):
        """Динамическое определение permissions на основе action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), CanManageStaffingTable()]
        else:
            return [permissions.IsAuthenticated(), CanViewStaffingTable()]

    def get_queryset(self):
        """Фильтрация queryset по области видимости пользователя"""
        user = self.request.user

        # Суперпользователь видит всё
        if user.is_superuser:
            return StaffUnit.objects.all()

        # Используем RBAC engine для фильтрации
        return get_user_scope_queryset(user, StaffUnit)

    # list() метод использует стандартную логику ModelViewSet
    # Фильтрация по ролям происходит в get_queryset()

    def retrieve(self, request, *args, **kwargs):
        """
        Получение детальной информации о штатной единице.
        Возвращает расширенный формат с дочерними единицами и статусами.
        """
        instance = self.get_object()
        serializer = StaffUnitDetailedSerializer(instance)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
        Проверка прав при создании штатной единицы
        - Пользователь может создавать только в своей области видимости
        """
        user = self.request.user
        division = serializer.validated_data.get('division')

        # Проверка что подразделение в области видимости пользователя
        if not user.is_superuser and hasattr(user, 'role_info'):
            # Создаем временный объект для проверки scope
            temp_obj = StaffUnit(division=division)
            if not check_permission(user, 'create_staffing_position', temp_obj):
                raise PermissionDenied(
                    "У вас нет прав для создания штатной единицы в этом подразделении"
                )

        serializer.save()

    def perform_update(self, serializer):
        """
        Проверка прав при обновлении штатной единицы
        - Пользователь может редактировать только в своей области видимости
        """
        user = self.request.user
        instance = self.get_object()

        # Проверка что объект в области видимости
        if not user.is_superuser:
            if not check_permission(user, 'edit_staffing_position', instance):
                raise PermissionDenied(
                    "У вас нет прав для редактирования этой штатной единицы"
                )

        serializer.save()

    def perform_destroy(self, instance):
        """
        Проверка прав при удалении штатной единицы
        - Пользователь может удалять только в своей области видимости
        """
        user = self.request.user

        # Проверка что объект в области видимости
        if not user.is_superuser:
            if not check_permission(user, 'delete_staffing_position', instance):
                raise PermissionDenied(
                    "У вас нет прав для удаления этой штатной единицы"
                )

        instance.delete()

    def update(self, request, *args, **kwargs):
        """
        Переопределенный метод UPDATE с поддержкой bulk update.

        Если в теле запроса есть поля 'children' или 'employee_statuses',
        используется bulk update. Иначе - стандартное обновление.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Проверка прав
        if not request.user.is_superuser:
            if not check_permission(request.user, 'edit_staffing_position', instance):
                raise PermissionDenied(
                    "У вас нет прав для редактирования этой штатной единицы"
                )

        # Проверяем, нужен ли bulk update
        if 'children' in request.data or 'employee_statuses' in request.data:
            return self._bulk_update(request, instance)

        # Стандартное обновление
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Возвращаем детальную информацию
        detailed_serializer = StaffUnitDetailedSerializer(instance)
        return Response(detailed_serializer.data)

    @transaction.atomic
    def _bulk_update(self, request, instance):
        """
        Bulk update штатной единицы, дочерних единиц и статусов сотрудников
        """
        bulk_serializer = StaffUnitBulkUpdateSerializer(data=request.data)
        bulk_serializer.is_valid(raise_exception=True)
        data = bulk_serializer.validated_data

        # 1. Обновляем основную штатную единицу
        if 'division' in data:
            instance.division = Division.objects.get(id=data['division'])
        if 'position' in data:
            from organization_management.apps.dictionaries.models import Position
            instance.position = Position.objects.get(id=data['position'])
        if 'employee' in data:
            from organization_management.apps.employees.models import Employee
            instance.employee = Employee.objects.get(id=data['employee']) if data['employee'] else None
        if 'vacancy' in data:
            instance.vacancy = Vacancy.objects.get(id=data['vacancy']) if data['vacancy'] else None
        if 'index' in data:
            instance.index = data['index']
        if 'parent_id' in data:
            instance.parent = StaffUnit.objects.get(id=data['parent_id']) if data['parent_id'] else None

        instance.save()

        # 2. Обновляем дочерние штатные единицы
        if 'children' in data:
            for child_data in data['children']:
                child_id = child_data.get('id')

                if child_id:
                    # Обновление существующей
                    try:
                        child = StaffUnit.objects.get(id=child_id)
                        # Проверка прав на дочернюю единицу
                        if not request.user.is_superuser:
                            if not check_permission(request.user, 'edit_staffing_position', child):
                                continue  # Пропускаем, если нет прав

                        if 'division' in child_data:
                            child.division = Division.objects.get(id=child_data['division'])
                        if 'position' in child_data:
                            from organization_management.apps.dictionaries.models import Position
                            child.position = Position.objects.get(id=child_data['position'])
                        if 'employee' in child_data:
                            from organization_management.apps.employees.models import Employee
                            child.employee = Employee.objects.get(id=child_data['employee']) if child_data['employee'] else None
                        if 'vacancy' in child_data:
                            child.vacancy = Vacancy.objects.get(id=child_data['vacancy']) if child_data['vacancy'] else None
                        if 'index' in child_data:
                            child.index = child_data['index']
                        if 'parent_id' in child_data:
                            child.parent = StaffUnit.objects.get(id=child_data['parent_id']) if child_data['parent_id'] else None

                        child.save()
                    except StaffUnit.DoesNotExist:
                        pass
                else:
                    # Создание новой дочерней единицы
                    division = Division.objects.get(id=child_data['division'])

                    # Проверка прав на создание
                    temp_obj = StaffUnit(division=division)
                    if not request.user.is_superuser:
                        if not check_permission(request.user, 'create_staffing_position', temp_obj):
                            continue  # Пропускаем, если нет прав

                    StaffUnit.objects.create(
                        division_id=child_data.get('division'),
                        position_id=child_data.get('position'),
                        employee_id=child_data.get('employee'),
                        vacancy_id=child_data.get('vacancy'),
                        index=child_data.get('index', 0),
                        parent_id=child_data.get('parent_id', instance.id)
                    )

        # 3. Обновляем статусы сотрудников
        if 'employee_statuses' in data:
            for status_data in data['employee_statuses']:
                employee_id = status_data['employee_id']

                try:
                    employee = Employee.objects.get(id=employee_id)

                    # Проверка прав на изменение статуса
                    if not request.user.is_superuser:
                        if not check_permission(request.user, 'change_employee_status', employee):
                            continue  # Пропускаем, если нет прав

                    # Создаем новый статус
                    EmployeeStatus.objects.create(
                        employee=employee,
                        status_type=status_data.get('status_type', 'in_service'),
                        state=status_data.get('state', 'active'),
                        start_date=status_data.get('start_date'),
                        end_date=status_data.get('end_date'),
                        comment=status_data.get('comment', ''),
                        created_by=request.user
                    )
                except Employee.DoesNotExist:
                    pass

        # Возвращаем обновленную штатную единицу с детальной информацией
        serializer = StaffUnitDetailedSerializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'put', 'patch', 'post'], url_path='directorate')
    def directorate_management(self, request):
        """
        Эндпоинт для управления штатным расписанием своего подразделения.

        ROLE_3: Управляет своим управлением (level=2)
        ROLE_6: Управляет своим отделом (level=3)
        ROLE_7: Управляет своим департаментом (level=1)

        GET: Получить все штатные единицы своего подразделения
        PUT/PATCH/POST: Обновить штатные единицы, сотрудников и их статусы

        НЕ использует область видимости для GET эндпоинта - показывает только свое подразделение.
        """
        user = request.user

        # Проверка что пользователь имеет ROLE_3, ROLE_6 или ROLE_7
        if not user.is_superuser:
            try:
                user_role = user.role_info  # OneToOneField
                if not user_role or user_role.role not in ['ROLE_3', 'ROLE_6', 'ROLE_7']:
                    return Response(
                        {'error': 'Доступ разрешен только для ROLE_3 (Начальник управления), ROLE_6 (Начальник отдела) или ROLE_7 (Начальник департамента)'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Exception as e:
                return Response(
                    {'error': f'У пользователя нет активной роли: {str(e)}'},
                    status=status.HTTP_403_FORBIDDEN
                )

        if request.method == 'GET':
            return self._directorate_get(request, user)
        else:  # PUT, PATCH, POST
            return self._directorate_update(request, user)

    def _directorate_get(self, request, user):
        """
        Получение всех штатных единиц своего подразделения с дочерними отделами.

        ROLE_3: управление + все дочерние отделы
        ROLE_6: отдел + все дочерние подразделения

        Возвращает ПЛОСКИЙ список (БЕЗ вложенного children), связи через parent_id.
        """
        # Определяем СОБСТВЕННОЕ подразделение пользователя (НЕ область видимости)
        division = self._get_user_own_division(user)

        if not division:
            return Response(
                {'error': 'Не удалось определить подразделение пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем все подразделения: само + все дочерние
        all_divisions = division.get_descendants(include_self=True)

        # Получаем ВСЕ штатные единицы из этих подразделений
        staff_units = StaffUnit.objects.filter(
            division__in=all_divisions
        ).select_related(
            'division', 'position', 'employee', 'vacancy'
        ).prefetch_related(
            'employee__statuses'
        ).order_by('tree_id', 'lft')

        # Создаем плоский список с полной информацией (БЕЗ children)
        result = []
        for unit in staff_units:
            unit_data = {
                'id': unit.id,
                'division': {
                    'id': unit.division.id,
                    'name': unit.division.name,
                } if unit.division else None,
                'position': {
                    'id': unit.position.id,
                    'name': unit.position.name,
                    'level': unit.position.level,
                } if unit.position else None,
                'employee': None,
                'vacancy': None,
                'index': unit.index,
                'parent_id': unit.parent_id,
            }

            # Employee с current_status
            if unit.employee:
                current_status = unit.employee.statuses.order_by('-created_at').first()
                unit_data['employee'] = {
                    'id': unit.employee.id,
                    'first_name': unit.employee.first_name,
                    'last_name': unit.employee.last_name,
                    'current_status': {
                        'status_type': current_status.status_type,
                        'state': current_status.state,
                    } if current_status else None
                }

            # Vacancy
            if unit.vacancy:
                unit_data['vacancy'] = {
                    'id': unit.vacancy.id,
                    'title': unit.vacancy.title,
                }

            result.append(unit_data)

        return Response({
            'division': {
                'id': division.id,
                'name': division.name,
                'code': division.code if hasattr(division, 'code') else None,
            },
            'staff_units': result,
            'total_count': len(result),
        })

    @transaction.atomic
    def _directorate_update(self, request, user):
        """Обновление штатных единиц, сотрудников и статусов"""
        from organization_management.apps.employees.api.serializers import EmployeeSerializer
        from organization_management.apps.statuses.api.serializers import EmployeeStatusSerializer

        # Определяем СОБСТВЕННОЕ подразделение пользователя (НЕ область видимости)
        division = self._get_user_own_division(user)

        if not division:
            return Response(
                {'error': 'Не удалось определить подразделение пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Работа ТОЛЬКО с управлением пользователя (БЕЗ дочерних подразделений)
        division_ids = [division.id]

        data = request.data
        updated_items = {
            'staff_units': 0,
            'employees': 0,
            'statuses': 0,
        }
        errors = []

        # 1. Обновление штатных единиц
        if 'staff_units' in data:
            for staff_unit_data in data['staff_units']:
                try:
                    staff_unit_id = staff_unit_data.get('id')
                    if not staff_unit_id:
                        errors.append({'staff_unit': 'ID штатной единицы обязателен'})
                        continue

                    # Проверяем что штатная единица принадлежит области видимости
                    staff_unit = StaffUnit.objects.get(id=staff_unit_id, division_id__in=division_ids)

                    # Обновляем поля штатной единицы
                    if 'division' in staff_unit_data and staff_unit_data['division'] in division_ids:
                        staff_unit.division = Division.objects.get(id=staff_unit_data['division'])
                    if 'position' in staff_unit_data:
                        from organization_management.apps.dictionaries.models import Position
                        staff_unit.position = Position.objects.get(id=staff_unit_data['position'])
                    if 'index' in staff_unit_data:
                        staff_unit.index = staff_unit_data['index']

                    staff_unit.save()
                    updated_items['staff_units'] += 1

                except StaffUnit.DoesNotExist:
                    errors.append({'staff_unit': f'Штатная единица {staff_unit_id} не найдена или нет доступа'})
                except Exception as e:
                    errors.append({'staff_unit': f'ID {staff_unit_id}: {str(e)}'})

        # 2. Обновление сотрудников
        if 'employees' in data:
            for employee_data in data['employees']:
                try:
                    employee_id = employee_data.get('id')
                    if not employee_id:
                        errors.append({'employee': 'ID сотрудника обязателен'})
                        continue

                    # Проверяем что сотрудник принадлежит области видимости
                    employee = Employee.objects.select_related('staff_unit__division').get(
                        id=employee_id,
                        staff_unit__division_id__in=division_ids
                    )

                    # Обновляем только разрешенные поля
                    allowed_fields = ['first_name', 'last_name', 'middle_name', 'iin', 'rank']
                    for field in allowed_fields:
                        if field in employee_data:
                            setattr(employee, field, employee_data[field])

                    employee.save()
                    updated_items['employees'] += 1

                except Employee.DoesNotExist:
                    errors.append({'employee': f'Сотрудник {employee_id} не найден или нет доступа'})
                except Exception as e:
                    errors.append({'employee': f'ID {employee_id}: {str(e)}'})

        # 3. Обновление/создание статусов сотрудников
        if 'employee_statuses' in data:
            for status_data in data['employee_statuses']:
                try:
                    employee_id = status_data.get('employee')
                    if not employee_id:
                        errors.append({'status': 'ID сотрудника обязателен'})
                        continue

                    # Проверяем что сотрудник принадлежит области видимости
                    employee = Employee.objects.select_related('staff_unit__division').get(
                        id=employee_id,
                        staff_unit__division_id__in=division_ids
                    )

                    status_id = status_data.get('id')

                    if status_id:
                        # Обновление существующего статуса
                        emp_status = EmployeeStatus.objects.get(
                            id=status_id,
                            employee=employee
                        )
                        serializer = EmployeeStatusSerializer(
                            emp_status,
                            data=status_data,
                            partial=True,
                            context={'request': request}
                        )
                    else:
                        # Создание нового статуса
                        serializer = EmployeeStatusSerializer(
                            data=status_data,
                            context={'request': request}
                        )

                    if serializer.is_valid():
                        serializer.save(created_by=user)
                        updated_items['statuses'] += 1
                    else:
                        errors.append({'status': f'Employee {employee_id}: {serializer.errors}'})

                except Employee.DoesNotExist:
                    errors.append({'status': f'Сотрудник {employee_id} не найден или нет доступа'})
                except EmployeeStatus.DoesNotExist:
                    errors.append({'status': f'Статус {status_id} не найден'})
                except Exception as e:
                    errors.append({'status': f'Employee {employee_id}: {str(e)}'})

        # Формируем ответ
        response_data = {
            'success': True,
            'updated': updated_items,
            'division': {
                'id': division.id,
                'name': division.name,
            }
        }

        if errors:
            response_data['errors'] = errors
            response_data['success'] = len(errors) < sum(updated_items.values())

        return Response(response_data, status=status.HTTP_200_OK)

    def _get_user_division(self, user):
        """Определяет подразделение пользователя на основе его роли (для области видимости)"""
        if user.is_superuser:
            # Для суперпользователя можно вернуть корневое подразделение
            return Division.objects.filter(level=0).first()

        try:
            # Получаем роль пользователя (OneToOneField)
            user_role = user.role_info

            if not user_role:
                return None

            # Используем effective_scope_division из роли
            return user_role.effective_scope_division

        except Exception:
            return None

    def _get_user_own_division(self, user):
        """
        Определяет СОБСТВЕННОЕ подразделение пользователя (для directorate endpoint).

        НЕ использует область видимости - возвращает именно подразделение где работает сотрудник:
        - ROLE_3: управление (level=2) - поднимается до управления если сотрудник в отделе
        - ROLE_6: отдел (level=3) - возвращает отдел как есть
        - ROLE_7: департамент (level=1) - поднимается до департамента

        Для ROLE_7 scope_division имеет приоритет (может быть указан вручную).
        Для ROLE_3 и ROLE_6: если scope_division указан вручную и НЕ на уровне департамента - использует его.
        """
        if user.is_superuser:
            return Division.objects.filter(level=0).first()

        try:
            user_role = user.role_info
            if not user_role:
                return None

            # Для ROLE_7: приоритет у scope_division если указан на уровне департамента
            if user_role.role == 'ROLE_7':
                # Приоритет 1: Если scope_division указан вручную на уровне департамента (level=1)
                if user_role.scope_division and user_role.scope_division.level == 1:
                    return user_role.scope_division

                # Приоритет 2: Автоматическое определение - поднимаемся до департамента
                if hasattr(user, 'employee'):
                    employee = user.employee
                    if hasattr(employee, 'staff_unit') and employee.staff_unit:
                        division = employee.staff_unit.division
                        # Поднимаемся до департамента (level=1)
                        current = division
                        while current and current.level > 1:
                            current = current.parent
                        if current and current.level == 1:
                            return current
                        return division

                # Приоритет 3: Если scope_division на любом уровне
                if user_role.scope_division:
                    # Если не департамент - поднимаемся до департамента
                    current = user_role.scope_division
                    while current and current.level > 1:
                        current = current.parent
                    if current and current.level == 1:
                        return current
                    return user_role.scope_division

                return None

            # Для ROLE_3 и ROLE_6: старая логика
            # Приоритет 1: Если scope_division указан вручную И он НЕ департамент (level != 1)
            # то используем его (это управление или отдел)
            if user_role.scope_division and user_role.scope_division.level != 1:
                return user_role.scope_division

            # Приоритет 2: Автоматическое определение через Employee → StaffUnit → Division
            if hasattr(user, 'employee'):
                employee = user.employee
                if hasattr(employee, 'staff_unit') and employee.staff_unit:
                    division = employee.staff_unit.division

                    # Для ROLE_3 (Начальник управления): поднимаемся до управления (level=2)
                    if user_role.role == 'ROLE_3':
                        current = division
                        # Поднимаемся вверх пока не достигнем level=2 (управление)
                        while current and current.level > 2:
                            current = current.parent
                        if current and current.level == 2:
                            return current
                        # Если не нашли level=2, возвращаем как есть
                        return division

                    # Для ROLE_6 (Начальник отдела): возвращаем отдел как есть
                    return division

            # Приоритет 3: Если scope_division на уровне департамента, но больше нечего вернуть
            # возвращаем его (хотя это неправильно для directorate endpoint для ROLE_3 и ROLE_6)
            if user_role.scope_division:
                return user_role.scope_division

            return None

        except Exception:
            return None
