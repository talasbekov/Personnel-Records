from django.db.models.query import Prefetch
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
                role_code = user_role.get_role_code() if user_role else None
                if not role_code or role_code not in ['ROLE_3', 'ROLE_6', 'ROLE_7']:
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
        elif request.method == 'POST':
            return self._directorate_create(request, user)
        else:  # PUT, PATCH
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
            Prefetch(
                'employee__statuses',
                queryset=EmployeeStatus.objects.filter(
                    state=EmployeeStatus.StatusState.ACTIVE
                ).order_by('-start_date')
            )
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

                # Если у сотрудника нет статуса, создаем дефолтный "в строю"
                if not current_status:
                    from django.utils import timezone
                    current_status = EmployeeStatus.objects.create(
                        employee=unit.employee,
                        status_type=EmployeeStatus.StatusType.IN_SERVICE,
                        start_date=timezone.now().date(),
                        state=EmployeeStatus.StatusState.ACTIVE,
                        comment='Автоматически создан при отсутствии статуса'
                    )

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

    def _generate_personnel_number(self):
        """Генерация уникального табельного номера"""
        from django.db.models import Max

        # Находим максимальный существующий номер
        max_number = Employee.objects.filter(
            personnel_number__regex=r'^\d+$'  # Только числовые номера
        ).aggregate(
            max_num=Max('personnel_number')
        )['max_num']

        if max_number:
            try:
                next_number = int(max_number) + 1
            except (ValueError, TypeError):
                next_number = 1
        else:
            next_number = 1

        # Форматируем с ведущими нулями (6 цифр)
        return str(next_number).zfill(6)

    @transaction.atomic
    def _directorate_create(self, request, user):
        """Создание новых штатных единиц и сотрудников"""
        from django.utils import timezone
        from django.core.exceptions import ValidationError

        # Определяем СОБСТВЕННОЕ подразделение пользователя
        division = self._get_user_own_division(user)

        if not division:
            return Response(
                {'error': 'Не удалось определить подразделение пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Работа с управлением пользователя И всеми дочерними подразделениями
        all_divisions = division.get_descendants(include_self=True)
        division_ids = list(all_divisions.values_list('id', flat=True))

        data = request.data
        created_items = {
            'employees': [],
            'staff_units': [],
        }
        errors = []

        # 1. СПЕРВА создаем всех сотрудников с savepoint для возможного отката
        if 'employees' in data:
            for employee_data in data['employees']:
                # Для создания - не должно быть ID
                if 'id' in employee_data:
                    errors.append({'employee': 'При создании не нужно указывать ID сотрудника'})
                    continue

                # Создаем savepoint для возможности отката если штатка не создастся
                sid = transaction.savepoint()

                try:
                    # Генерируем уникальный табельный номер
                    personnel_number = self._generate_personnel_number()

                    # Создаем сотрудника
                    employee = Employee(
                        personnel_number=personnel_number,
                        first_name=employee_data.get('first_name', ''),
                        last_name=employee_data.get('last_name', ''),
                        middle_name=employee_data.get('middle_name', ''),
                        iin=employee_data.get('iin', ''),
                    )

                    # Валидация перед сохранением (проверит ИИН)
                    employee.full_clean()
                    employee.save()

                    # Обработка rank если указан
                    if 'rank' in employee_data and employee_data['rank']:
                        from organization_management.apps.dictionaries.models import Rank
                        try:
                            rank = Rank.objects.get(id=employee_data['rank'])
                            employee.rank = rank
                            employee.save()
                        except Rank.DoesNotExist:
                            errors.append({'employee': f'Созданный ID {employee.id}: Звание с ID {employee_data["rank"]} не найдено'})

                    # Автоматически создаем статус "в строю"
                    EmployeeStatus.objects.create(
                        employee=employee,
                        status_type=EmployeeStatus.StatusType.IN_SERVICE,
                        start_date=timezone.now().date(),
                        state=EmployeeStatus.StatusState.ACTIVE,
                        comment='Автоматически создан при создании сотрудника',
                        created_by=user
                    )

                    # Сразу после создания сотрудника ищем его по ИИН и personnel_number
                    # чтобы получить ID для привязки к штатной единице
                    found_employee = Employee.objects.get(
                        iin=employee.iin,
                        personnel_number=employee.personnel_number
                    )
                    employee_id_for_staff_unit = found_employee.id

                    created_items['employees'].append({
                        'id': employee.id,
                        'personnel_number': employee.personnel_number,
                        'first_name': employee.first_name,
                        'last_name': employee.last_name,
                        'middle_name': employee.middle_name,
                        'iin': employee.iin,
                        '_employee_id_for_staff_unit': employee_id_for_staff_unit,
                        '_savepoint_id': sid,  # Сохраняем savepoint для возможного отката
                    })

                    # НЕ коммитим savepoint здесь - оставляем его открытым
                    # Он будет закоммичен автоматически при успешном создании штатной единицы
                    # Или откачен, если штатная единица не создастся

                except ValidationError as ve:
                    # Ошибка валидации - откатываем создание сотрудника
                    transaction.savepoint_rollback(sid)
                    errors.append({'employee': f'Ошибка валидации: {ve}'})
                except Exception as e:
                    # Любая ошибка - откатываем создание сотрудника
                    transaction.savepoint_rollback(sid)
                    errors.append({'employee': f'Ошибка создания сотрудника: {str(e)}'})

        # Вспомогательная функция для отката savepoint сотрудника
        def rollback_employee_savepoint(idx):
            """Откатывает savepoint сотрудника по индексу"""
            if idx < len(created_items['employees']):
                emp_data = created_items['employees'][idx]
                savepoint_id = emp_data.get('_savepoint_id')
                if savepoint_id:
                    try:
                        transaction.savepoint_rollback(savepoint_id)
                        # Удаляем из списка созданных
                        employee_id = emp_data.get('_employee_id_for_staff_unit')
                        created_items['employees'] = [
                            e for e in created_items['employees']
                            if e.get('_employee_id_for_staff_unit') != employee_id
                        ]
                    except Exception:
                        pass  # Игнорируем ошибки отката

        # 2. ПОТОМ создаем штатные единицы и привязываем сотрудников по ИИН
        if 'staff_units' in data:
            for idx, staff_unit_data in enumerate(data['staff_units']):
                # Для создания - не должно быть ID
                if 'id' in staff_unit_data:
                    rollback_employee_savepoint(idx)
                    errors.append({'staff_unit': 'При создании не нужно указывать ID штатной единицы'})
                    continue

                try:
                    # Проверяем что подразделение в области доступа
                    division_id = staff_unit_data.get('division')
                    if not division_id:
                        rollback_employee_savepoint(idx)
                        errors.append({'staff_unit': 'Не указано подразделение (division)'})
                        continue

                    if division_id not in division_ids:
                        rollback_employee_savepoint(idx)
                        errors.append({'staff_unit': f'Подразделение {division_id} не в вашей области доступа'})
                        continue

                    position_id = staff_unit_data.get('position')
                    if not position_id:
                        rollback_employee_savepoint(idx)
                        errors.append({'staff_unit': 'Не указана должность (position)'})
                        continue

                    # Генерируем уникальный index для этой комбинации division+position
                    from django.db.models import Max
                    max_index = StaffUnit.objects.filter(
                        division_id=division_id,
                        position_id=position_id
                    ).aggregate(max_idx=Max('index'))['max_idx']

                    if max_index is not None:
                        next_index = max_index + 1
                    else:
                        next_index = staff_unit_data.get('index', 1)

                    # Получаем employee_id из созданных сотрудников по индексу
                    employee_id = None
                    if idx < len(created_items['employees']):
                        # Берём ID сотрудника по тому же индексу
                        employee_id = created_items['employees'][idx].get('_employee_id_for_staff_unit')

                    # Если не нашли по индексу - пробуем найти по ИИН и personnel_number
                    if not employee_id:
                        iin = staff_unit_data.get('iin')
                        personnel_number = staff_unit_data.get('personnel_number')

                        if iin and personnel_number:
                            # Поиск по обоим полям для точности
                            try:
                                found_employee = Employee.objects.get(
                                    iin=iin,
                                    personnel_number=personnel_number
                                )
                                employee_id = found_employee.id
                            except Employee.DoesNotExist:
                                errors.append({'staff_unit': f'Индекс {idx}: Сотрудник с ИИН {iin} и табельным номером {personnel_number} не найден'})
                            except Employee.MultipleObjectsReturned:
                                errors.append({'staff_unit': f'Индекс {idx}: Найдено несколько сотрудников с ИИН {iin} и табельным номером {personnel_number}'})
                        elif iin:
                            # Поиск только по ИИН
                            try:
                                found_employee = Employee.objects.get(iin=iin)
                                employee_id = found_employee.id
                            except Employee.DoesNotExist:
                                errors.append({'staff_unit': f'Индекс {idx}: Сотрудник с ИИН {iin} не найден'})
                            except Employee.MultipleObjectsReturned:
                                errors.append({'staff_unit': f'Индекс {idx}: Найдено несколько сотрудников с ИИН {iin}'})

                    # Если сотрудник не найден - пропускаем создание штатной единицы
                    if not employee_id:
                        rollback_employee_savepoint(idx)
                        errors.append({'staff_unit': f'Индекс {idx}: Не удалось найти сотрудника для привязки. Штатная единица не создана.'})
                        continue

                    # Автоматическое определение родителя
                    parent_unit = None

                    try:
                        # 1. Получаем объект должности для проверки уровня
                        from organization_management.apps.dictionaries.models import Position
                        current_position = Position.objects.get(id=position_id)

                        # 2. Ищем начальника ВНУТРИ текущего подразделения
                        # Начальник - это тот, у кого уровень должности МЕНЬШЕ (выше ранг)
                        internal_boss = StaffUnit.objects.filter(
                            division_id=division_id,
                            position__level__lt=current_position.level
                        ).order_by('position__level').first()

                        if internal_boss:
                            parent_unit = internal_boss
                        else:
                            # 3. Если внутри начальника нет, ищем в РОДИТЕЛЬСКОМ подразделении
                            current_division = Division.objects.get(id=division_id)
                            if current_division.parent:
                                # В родительском подразделении ищем сотрудника с самым высоким рангом (min level)
                                parent_division_boss = StaffUnit.objects.filter(
                                    division=current_division.parent
                                ).order_by('position__level').first()

                                if parent_division_boss:
                                    parent_unit = parent_division_boss

                    except Exception as e:
                        # Логируем ошибку определения родителя, но не прерываем создание
                        print(f"Ошибка определения родителя: {e}")
                        pass

                    # Создаем штатную единицу
                    staff_unit = StaffUnit.objects.create(
                        division_id=division_id,
                        position_id=position_id,
                        index=next_index,
                        employee_id=employee_id,  # Привязываем сотрудника по найденному ID
                        parent_id=parent_unit.id if parent_unit else None
                    )

                    created_items['staff_units'].append({
                        'id': staff_unit.id,
                        'division': staff_unit.division_id,
                        'position': staff_unit.position_id,
                        'employee': staff_unit.employee_id,
                        'index': staff_unit.index,
                    })

                    # Штатная единица успешно создана - НЕ коммитим savepoint
                    # Он закоммитится автоматически в конце основной транзакции

                except Exception as e:
                    # Если штатная единица не создалась, откатываем создание связанного сотрудника через savepoint
                    if employee_id:
                        # Ищем сотрудника в списке созданных по employee_id
                        employee_found = False
                        for emp_data in created_items['employees']:
                            if emp_data.get('_employee_id_for_staff_unit') == employee_id:
                                employee_found = True
                                # Получаем savepoint этого сотрудника и откатываем его
                                savepoint_id = emp_data.get('_savepoint_id')
                                if savepoint_id:
                                    try:
                                        transaction.savepoint_rollback(savepoint_id)
                                        # Удаляем из списка созданных сотрудников
                                        created_items['employees'] = [
                                            emp for emp in created_items['employees']
                                            if emp.get('_employee_id_for_staff_unit') != employee_id
                                        ]
                                        errors.append({'staff_unit': f'Индекс {idx}: Штатная единица не создана, сотрудник откачен (ID {employee_id})'})
                                    except Exception as rollback_error:
                                        errors.append({'staff_unit': f'Индекс {idx}: Ошибка отката сотрудника (ID {employee_id}): {str(rollback_error)}'})
                                else:
                                    errors.append({'staff_unit': f'Индекс {idx}: Savepoint не найден для сотрудника (ID {employee_id})'})
                                break

                        if not employee_found:
                            errors.append({'staff_unit': f'Индекс {idx}: Сотрудник с ID {employee_id} не найден в списке созданных'})

                    errors.append({'staff_unit': f'Индекс {idx}: Ошибка создания штатной единицы: {str(e)}'})

        return Response({
            'success': True,
            'created': created_items,
            'errors': errors if errors else None,
        }, status=status.HTTP_201_CREATED)

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

        # Работа с управлением пользователя И всеми дочерними подразделениями
        all_divisions = division.get_descendants(include_self=True)
        division_ids = list(all_divisions.values_list('id', flat=True))

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
                    allowed_fields = ['first_name', 'last_name', 'middle_name', 'iin']
                    for field in allowed_fields:
                        if field in employee_data:
                            setattr(employee, field, employee_data[field])

                    # Обработка rank отдельно (это ForeignKey)
                    if 'rank' in employee_data:
                        rank_id = employee_data['rank']
                        if rank_id:
                            from organization_management.apps.dictionaries.models import Rank
                            try:
                                rank = Rank.objects.get(id=rank_id)
                                employee.rank = rank
                            except Rank.DoesNotExist:
                                errors.append({'employee': f'ID {employee_id}: Звание с ID {rank_id} не найдено'})
                                continue
                        else:
                            employee.rank = None

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

            role_code = user_role.get_role_code()

            # Для ROLE_7: приоритет у scope_division если указан на уровне департамента
            if role_code == 'ROLE_7':
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
                    if role_code == 'ROLE_3':
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


class DivisionStatisticsViewSet(viewsets.ViewSet):
    """
    ViewSet для получения статистики по подразделениям в зависимости от роли пользователя.
    Показывает количество департаментов, управлений, отделов, штатных единиц, сотрудников и вакансий.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None  # ViewSet возвращает статистику в виде dict

    def list(self, request):
        """
        Возвращает статистику по области видимости пользователя.
        """
        user = request.user

        # Определяем область видимости пользователя
        scope_division = self._get_user_scope_division(user)

        if not scope_division:
            return Response({
                'detail': 'Не удалось определить область видимости пользователя'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Получаем все подразделения в области видимости (включая само подразделение)
        divisions_in_scope = scope_division.get_descendants(include_self=True)
        division_ids = list(divisions_in_scope.values_list('id', flat=True))

        # Подсчет по типам подразделений
        departments_count = divisions_in_scope.filter(division_type=Division.DivisionType.DEPARTMENT).count()
        directorates_count = divisions_in_scope.filter(division_type=Division.DivisionType.DIRECTORATE).count()
        divisions_count = divisions_in_scope.filter(division_type=Division.DivisionType.DIVISION).count()

        # Подсчет штатных единиц
        staff_units_count = StaffUnit.objects.filter(division_id__in=division_ids).count()

        # Подсчет сотрудников (штатные единицы с заполненным employee)
        employees_count = StaffUnit.objects.filter(
            division_id__in=division_ids,
            employee__isnull=False
        ).count()

        # Подсчет вакансий (штатные единицы без employee)
        vacancies_count = StaffUnit.objects.filter(
            division_id__in=division_ids,
            employee__isnull=True
        ).count()

        # Статистика по каждому департаменту
        departments_stats = []
        for dept in divisions_in_scope.filter(division_type=Division.DivisionType.DEPARTMENT):
            dept_descendants = dept.get_descendants(include_self=True)
            dept_division_ids = list(dept_descendants.values_list('id', flat=True))

            directorates_in_dept = dept_descendants.filter(division_type=Division.DivisionType.DIRECTORATE).count()
            divisions_in_dept = dept_descendants.filter(division_type=Division.DivisionType.DIVISION).count()
            staff_units_in_dept = StaffUnit.objects.filter(division_id__in=dept_division_ids).count()
            employees_in_dept = StaffUnit.objects.filter(
                division_id__in=dept_division_ids,
                employee__isnull=False
            ).count()
            vacancies_in_dept = StaffUnit.objects.filter(
                division_id__in=dept_division_ids,
                employee__isnull=True
            ).count()

            departments_stats.append({
                'department_id': dept.id,
                'department_name': dept.name,
                'directorates_count': directorates_in_dept,
                'divisions_count': divisions_in_dept,
                'staff_units_count': staff_units_in_dept,
                'employees_count': employees_in_dept,
                'vacancies_count': vacancies_in_dept,
            })

        # Статистика по управлениям
        directorates_stats = []
        for directorate in divisions_in_scope.filter(division_type=Division.DivisionType.DIRECTORATE):
            dir_descendants = directorate.get_descendants(include_self=True)
            dir_division_ids = list(dir_descendants.values_list('id', flat=True))

            divisions_in_dir = dir_descendants.filter(division_type=Division.DivisionType.DIVISION).count()
            staff_units_in_dir = StaffUnit.objects.filter(division_id__in=dir_division_ids).count()
            employees_in_dir = StaffUnit.objects.filter(
                division_id__in=dir_division_ids,
                employee__isnull=False
            ).count()
            vacancies_in_dir = StaffUnit.objects.filter(
                division_id__in=dir_division_ids,
                employee__isnull=True
            ).count()

            directorates_stats.append({
                'directorate_id': directorate.id,
                'directorate_name': directorate.name,
                'divisions_count': divisions_in_dir,
                'staff_units_count': staff_units_in_dir,
                'employees_count': employees_in_dir,
                'vacancies_count': vacancies_in_dir,
            })

        # Статистика по отделам
        divisions_stats = []
        for division in divisions_in_scope.filter(division_type=Division.DivisionType.DIVISION):
            division_descendants = division.get_descendants(include_self=True)
            division_division_ids = list(division_descendants.values_list('id', flat=True))

            staff_units_in_division = StaffUnit.objects.filter(division_id__in=division_division_ids).count()
            employees_in_division = StaffUnit.objects.filter(
                division_id__in=division_division_ids,
                employee__isnull=False
            ).count()
            vacancies_in_division = StaffUnit.objects.filter(
                division_id__in=division_division_ids,
                employee__isnull=True
            ).count()

            divisions_stats.append({
                'division_id': division.id,
                'division_name': division.name,
                'staff_units_count': staff_units_in_division,
                'employees_count': employees_in_division,
                'vacancies_count': vacancies_in_division,
            })

        return Response({
            'scope_division': {
                'id': scope_division.id,
                'name': scope_division.name,
                'division_type': scope_division.division_type,
            },
            'summary': {
                'departments_count': departments_count,
                'directorates_count': directorates_count,
                'divisions_count': divisions_count,
                'staff_units_count': staff_units_count,
                'employees_count': employees_count,
                'vacancies_count': vacancies_count,
            },
            'departments': departments_stats,
            'directorates': directorates_stats,
            'divisions': divisions_stats,
        })

    def _get_user_scope_division(self, user):
        """Определяет область видимости пользователя"""
        if user.is_superuser:
            # Для суперпользователя возвращаем корневое подразделение
            return Division.objects.filter(parent__isnull=True).first()

        try:
            if hasattr(user, 'role_info'):
                user_role = user.role_info
                return user_role.effective_scope_division
        except Exception:
            pass

        return None
