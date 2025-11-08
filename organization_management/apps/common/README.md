# Система ролей и прав доступа (RBAC)

## Обзор

Система RBAC обеспечивает управление доступом ко **ВСЕМ** моделям приложения:
- **StaffUnit** (штатные единицы)
- **Vacancy** (вакансии)
- **Employee** (сотрудники)
- **EmployeeStatus** (статусы сотрудников)
- **Secondment** (прикомандирование/откомандирование)
- **Division** (подразделения)
- **Report** (отчёты)
- И другие модели системы

## 6 ролей системы

### ROLE_1: Наблюдатель организации
- **Область видимости**: Вся организация
- **Права**: Только просмотр
- **Модели**: Все модели (чтение)
- **Пример**: Руководитель высшего звена, аналитик

### ROLE_2: Наблюдатель департамента
- **Область видимости**: Департамент
- **Права**: Только просмотр департамента
- **Модели**: Все модели департамента (чтение)
- **Пример**: Заместитель начальника департамента

### ROLE_3: Начальник управления
- **Область видимости**: 
  - Просмотр: Весь департамент
  - Редактирование: Только управление
- **Права**: 
  - Изменение статусов в управлении
  - Откомандирование из управления
  - Одобрение прикомандирования в управление
- **Модели**: Division, Employee, EmployeeStatus, Secondment

### ROLE_4: Системный администратор
- **Область видимости**: Вся организация
- **Права**: ВСЕ операции
- **Модели**: Все модели (полный доступ)
- **Пример**: Начальник кадровой службы

### ROLE_5: Кадровый администратор
- **Область видимости**: Подразделение (департамент/управление/отдел)
- **Права**:
  - Управление штатным расписанием
  - Управление вакансиями
  - Прием и перемещение сотрудников
  - НЕ может изменять статусы
- **Модели**: StaffUnit, Vacancy, Employee

### ROLE_6: Начальник отдела
- **Область видимости**:
  - Просмотр: Весь департамент
  - Редактирование: Только отдел
- **Права**: Изменение статусов в отделе
- **Модели**: EmployeeStatus

## Использование в коде

### 1. Проверка прав

```python
from organization_management.apps.common.rbac import check_permission

# Проверка без объекта
if check_permission(user, 'view_employees'):
    employees = Employee.objects.all()

# Проверка с объектом (учитывает область видимости)
employee = Employee.objects.get(id=1)
if check_permission(user, 'edit_employee', employee):
    employee.save()
```

### 2. Фильтрация queryset

```python
from organization_management.apps.common.rbac import get_user_scope_queryset

# Автоматическая фильтрация по области видимости
employees = get_user_scope_queryset(user, Employee)
statuses = get_user_scope_queryset(user, EmployeeStatus)
secondments = get_user_scope_queryset(user, Secondment)
```

### 3. В DRF ViewSet

```python
from organization_management.apps.common.drf_permissions import RoleBasedPermission

class EmployeeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    
    # Маппинг actions на права
    permission_map = {
        'list': 'view_employees',
        'retrieve': 'view_employee_details',
        'create': 'hire_employee',
        'update': 'edit_employee',
    }
    
    def get_queryset(self):
        return get_user_scope_queryset(self.request.user, Employee)
```

## Поддерживаемые модели

### Как система определяет подразделение объекта

| Модель | Путь к Division |
|--------|-----------------|
| Division | сам объект |
| StaffUnit | `obj.division` |
| Vacancy | `obj.staff_unit.division` |
| Employee | `obj.staff_unit.division` |
| EmployeeStatus | `obj.employee.staff_unit.division` |
| Secondment | `obj.from_division` или `obj.to_division` |
| StatusDocument | `obj.status.employee.staff_unit.division` |
| Report | `obj.division` |

### Автоматическая фильтрация queryset

```python
# Для каждой модели автоматически применяется правильный фильтр
Division:        division.id IN [...]
StaffUnit:       staff_unit.division__id IN [...]
Vacancy:         vacancy.staff_unit__division__id IN [...]
Employee:        employee.staff_unit__division__id IN [...]
EmployeeStatus:  status.employee__staff_unit__division__id IN [...]
Secondment:      secondment.from_division__id IN [...]
```

## Особые правила

### Откомандирование (Роль-3, Роль-6)

При откомандировании начальник **ТЕРЯЕТ** права на редактирование:

```python
# До откомандирования
check_permission(user, 'change_employee_status', status)  # True

# После откомандирования
user.role_info.is_seconded = True
check_permission(user, 'change_employee_status', status)  # False
```

### Иерархическая логика (Роль-3, Роль-6)

Видят больше, чем могут редактировать:

```python
# Роль-3: Начальник управления
check_permission(user, 'view_employees')        # True - весь департамент
check_permission(user, 'edit_employee', emp1)   # True - если в управлении
check_permission(user, 'edit_employee', emp2)   # False - если в другом управлении
```

## JWT Токен

Информация о роли автоматически включается в JWT:

```json
{
  "role": "ROLE_3",
  "role_name": "Начальник управления",
  "scope_division_id": 5,
  "scope_division_name": "Управление А",
  "is_seconded": false,
  "can_edit_statuses": true,
  "is_admin": false,
  "is_hr_admin": false,
  "is_manager": true
}
```

## Создание тестовых пользователей

```bash
docker compose exec web python manage.py setup_demo_roles
```

Создаёт 3 пользователя:
- `demo_observer_org` / `demo123` - Наблюдатель организации
- `demo_admin` / `demo123` - Системный администратор  
- `demo_hr_admin` / `demo123` - Кадровый администратор

## Расширение системы

### Добавление новых прав

1. Добавьте permission в Meta модели:

```python
class MyModel(models.Model):
    # ...
    class Meta:
        permissions = [
            ('my_custom_permission', 'Описание права'),
        ]
```

2. Добавьте право в матрицу ролей (`rbac.py`):

```python
ROLE_PERMISSIONS = {
    'ROLE_4': [
        # ... existing permissions
        'my_custom_permission',
    ],
}
```

3. Создайте миграцию:

```bash
python manage.py makemigrations
python manage.py migrate
```

### Добавление поддержки новой модели

1. Обновите `get_object_division()` в `rbac.py`
2. Добавьте маппинг в `_get_division_field_for_model()`
3. Протестируйте фильтрацию queryset

## Интеграция с Django Admin

Роли полностью интегрированы с Django Admin:

1. Перейдите в http://localhost:8000/admin/
2. Раздел "Общие компоненты" → "Роли пользователей"
3. Создайте/редактируйте роли

При редактировании User в админке отображается inline с ролью.

## Безопасность

- ✅ Суперпользователь имеет все права
- ✅ Роль-4 имеет все права
- ✅ Все остальные роли ограничены областью видимости
- ✅ Откомандированные начальники теряют права на редактирование
- ✅ Автоматическая фильтрация queryset предотвращает доступ к чужим данным
