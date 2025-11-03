# Система "Расход Организации"

Это документация для проектной работы по созданию системы управления расходом личного состава организации. Структура этого файла следует структуре заданий. Документ заполняется по мере работы над решением.

# Задание 1. Анализ и планирование

<aside>

**О проекте**

Система "Расход Организации" предназначена для управления расходом личного состава организации с иерархической структурой, отслеживания статусов сотрудников, генерации отчетности и управления кадровыми процессами.

**Текущее состояние**

В настоящий момент существует базовое монолитное приложение на Django с СУБД PostgreSQL, которое позволяет:
- Просматривать организационную структуру
- Учитывать сотрудников и их должности
- Отмечать базовые статусы (в строю, отпуск, больничный)
- Генерировать простые отчеты в формате Excel

Все операции выполняются синхронно. Нет асинхронной обработки задач, сложные кадровые процессы не поддерживаются, отсутствует система прикомандирования/откомандирования, многоуровневые роли доступа и детальный аудит операций.

**Целевая система**

Необходимо создать enterprise-уровень монолитную систему с модульной архитектурой, которая обеспечит:
- Гибкую многоуровневую организационную структуру (Компания → Департаменты → Управления → Отделы)
- Детальную ролевую модель с 6 ролями и ограничениями по подразделениям
- Комплексное управление статусами сотрудников с планированием на будущее
- Систему прикомандирования/откомандирования с согласованиями
- Управление штатным расписанием и вакансиями
- Автоматизированную генерацию отчетов в форматах .docx, .xlsx, .pdf
- Полный аудит и историю всех операций
- Real-time уведомления через WebSocket

**Требования к системе**

- Модульная архитектура в рамках монолита для логического разделения функций
- Асинхронная обработка длительных операций (генерация отчетов) через Celery
- Интеграция с внешней системой авторизации через JWT
- Чистая архитектура с разделением на слои (API, Application, Domain, Infrastructure)
- Применение паттернов DDD для управления сложностью доменной логики
- Высокая производительность и оптимизация запросов к БД

**Команда проекта**

- Команда разработки Backend (1 человек) — разработка модулей
- Команда разработки Frontend (1 человек) — создание веб-интерфейса
- Команда QA (1 человек) — тестирование системы
- Архитектор решения (1 человек) — проектирование архитектуры
- DevOps инженер (1 человек) — инфраструктура и развертывание

**Текущие показатели**

- Количество пользователей: ~50
- Количество сотрудников в системе: ~500
- Количество подразделений: ~30
- Среднее время генерации отчета: 15-20 секунд (блокирует пользователя)

**Целевые показатели**

- Поддержка до 500 пользователей
- Учет до 5000 сотрудников
- До 200 подразделений
- Асинхронная генерация отчетов (результат по готовности)
- Время отклика API < 500ms для 95% запросов

</aside>

### 1. Описание функциональности монолитного приложения

**Управление организационной структурой:**

- Пользователи могут просматривать дерево организации
- Ограниченные возможности создания/редактирования подразделений (только администратор)
- Нет поддержки гибкой иерархии (только фиксированная структура: компания → департамент → отдел)
- Отсутствует управление связями между подразделениями
- Нет поддержки управлений как промежуточного уровня

**Учет сотрудников:**

- Базовая информация о сотрудниках (ФИО, должность, фото)
- Привязка к одному подразделению
- Нет поддержки истории переводов
- Отсутствует управление штатным расписанием
- Нет системы вакансий
- Невозможно назначить должность "за счёт" другой должности

**Управление статусами:**

- Ограниченный набор статусов (в строю, отпуск, больничный)
- Статус можно установить только на текущую дату
- Нет планирования статусов на будущее
- Отсутствует валидация пересечений статусов
- Нет поддержки прикомандирования/откомандирования
- Отсутствует автоматическая эскалация изменений статусов

**Генерация отчетов:**

- Только простые Excel-отчеты
- Синхронная генерация (пользователь ждет)
- Нет шаблонов документов для .docx
- Отсутствует генерация PDF
- Невозможно сохранить историю отчетов
- Нет фильтрации и группировки данных

**Система прав доступа:**

- Только две роли: администратор и пользователь
- Нет детальной матрицы прав
- Отсутствует разграничение доступа по подразделениям
- Нет роли кадрового администратора подразделения
- Невозможно ограничить редактирование своим управлением/отделом

**Аудит и история:**

- Минимальное логирование операций
- Нет детальной истории изменений
- Отсутствует возможность восстановления данных
- Нет журнала доступа
- Невозможно отследить, кто и когда изменил данные

**Уведомления:**

- Отсутствует система уведомлений
- Нет информирования о изменениях статусов
- Отсутствуют оповещения о прикомандировании
- Нет напоминаний о истечении отпусков/командировок

### 2. Анализ архитектуры монолитного приложения

**Технический стек:**

- **Язык программирования:** Python (Django)
- **Framework:** Django + Django REST Framework
- **База данных:** PostgreSQL (одна БД для всех данных)
- **Архитектура:** монолитное приложение
- **Взаимодействие:** синхронные HTTP-запросы
- **Аутентификация:** Session-based (Django sessions)
- **Развёртывание:** один сервер с Gunicorn + Nginx

**Особенности текущей архитектуры:**

- Все модули в одном приложении (users, divisions, employees, statuses, reports)
- Единая база данных со всеми таблицами
- Нет разделения на слои (бизнес-логика смешана с контроллерами)
- Отсутствие очередей сообщений для асинхронных задач
- Генерация отчетов выполняется в основном потоке (блокирует запрос)
- Все файлы хранятся на том же сервере в file system
- Нет кэширования (каждый запрос к БД)

**Проблемы текущей реализации:**

- Нет четкого разделения на слои (все перемешано)
- Отсутствие паттернов проектирования
- Бизнес-логика размазана по views и models
- Сложность тестирования из-за связанности компонентов
- Долгие операции (генерация отчетов) блокируют другие запросы
- Нет изоляции модулей - изменение в одном месте влияет на другие

### 3. Определение доменов и границы контекстов

**Домен: Управление организацией (Organization Management)** [Core Domain]

  - **Поддомены:**
  
  1. **Организационная структура (Organizational Structure)** [Core]
    - **Контексты:**
      - Управление подразделениями (Division Management Context)
        - сущности: Organization, Department, Directorate, Division
        - объекты-значения: DivisionType, DivisionHierarchyPath
        - агрегаты: OrganizationHierarchy (корень: Organization)
        - репозитории: OrganizationRepository, DivisionRepository
        - сервисы: HierarchyNavigationService, DivisionStructureService
  
  2. **Кадровое управление (Personnel Management)** [Core]
    - **Контексты:**
      - Управление сотрудниками (Employee Management Context)
        - сущности: Employee, Position, PositionAssignment
        - объекты-значения: FullName, Photo, EmploymentPeriod, Rank
        - агрегаты: Employee (корень: Employee)
        - репозитории: EmployeeRepository, PositionRepository
        - сервисы: EmployeeOnboardingService, EmployeeOffboardingService, PositionAssignmentService
      
      - Штатное расписание (Staffing Table Context)
        - сущности: StaffingPosition, Vacancy
        - объекты-значения: PositionQuota, VacancyStatus
        - агрегаты: StaffingTable (корень: Division)
        - репозитории: StaffingTableRepository, VacancyRepository
        - сервисы: VacancyManagementService, StaffingQuotaService
  
  3. **Управление статусами (Status Management)** [Core]
    - **Контексты:**
      - Статусы сотрудников (Employee Status Context)
        - сущности: EmployeeStatus, StatusSchedule
        - объекты-значения: StatusType, StatusPeriod, StatusComment
        - агрегаты: EmployeeStatusHistory (корень: Employee)
        - репозитории: EmployeeStatusRepository, StatusScheduleRepository
        - сервисы: StatusAssignmentService, StatusPlanningService, StatusValidationService

**Домен: Командирование (Secondment Management)** [Supporting Domain]

  - **Поддомены:**
  
  1. **Прикомандирование/Откомандирование (Secondment)** [Supporting]
    - **Контексты:**
      - Процесс командирования (Secondment Process Context)
        - сущности: SecondmentRequest, SecondmentApproval
        - объекты-значения: SecondmentPeriod, SecondmentType, ApprovalStatus
        - агрегаты: Secondment (корень: SecondmentRequest)
        - репозитории: SecondmentRepository
        - сервисы: SecondmentProcessService, SecondmentApprovalService, SecondmentNotificationService

**Домен: Отчетность и аналитика (Reporting & Analytics)** [Supporting Domain]

  - **Поддомены:**
  
  1. **Генерация отчетов (Report Generation)** [Supporting]
    - **Контексты:**
      - Создание документов (Document Generation Context)
        - сущности: Report, ReportTemplate, ReportJob
        - объекты-значения: ReportFormat (docx/xlsx/pdf), ReportPeriod, ReportScope
        - агрегаты: ReportRequest (корень: Report)
        - репозитории: ReportRepository, ReportTemplateRepository, ReportJobRepository
        - сервисы: ReportGenerationService, DocumentExportService, DataAggregationService
      
      - Хранилище отчетов (Report Storage Context)
        - сущности: GeneratedReport
        - объекты-значения: FileMetadata, ExpirationDate
        - агрегаты: ReportArchive (корень: GeneratedReport)
        - репозитории: ReportArchiveRepository
        - сервисы: ReportStorageService, ReportCleanupService

**Домен: Контроль доступа и безопасность (Access Control & Security)** [Generic Domain]

  - **Поддомены:**
  
  1. **Управление правами (Authorization)** [Generic]
    - **Контексты:**
      - RBAC (Role-Based Access Control Context)
        - сущности: User, Role, Permission
        - объекты-значения: RoleType (Роль-1..6), PermissionScope, DivisionAccess
        - агрегаты: UserProfile (корень: User)
        - репозитории: UserRepository, RoleRepository, PermissionRepository
        - сервисы: AuthorizationService, PermissionCheckService
  
  2. **Аудит (Audit Logging)** [Generic]
    - **Контексты:**
      - Журнал операций (Audit Log Context)
        - сущности: AuditEntry
        - объекты-значения: AuditAction, AuditTimestamp, AuditMetadata
        - агрегаты: AuditLog (корень: AuditEntry)
        - репозитории: AuditLogRepository
        - сервисы: AuditLoggingService, AuditQueryService

**Домен: Справочники (Reference Data)** [Generic Domain]

  - **Поддомены:**
  
  1. **Управление справочниками (Dictionary Management)** [Generic]
    - **Контексты:**
      - Управление должностями (Position Management Context)
        - сущности: PositionCatalog
        - объекты-значения: PositionTitle, PositionLevel
        - агрегаты: PositionHierarchy (корень: PositionCatalog)
        - репозитории: PositionCatalogRepository
        - сервисы: PositionHierarchyService, PositionValidationService

### 4. Целевая архитектура монолита

**Преимущества улучшенного монолита:**

✅ **Простота развертывания** - одно приложение, один процесс
✅ **Атомарные транзакции** - операции в рамках одной БД
✅ **Простота отладки** - весь код в одном проекте
✅ **Меньше накладных расходов** - нет сетевых вызовов между модулями
✅ **Проще для малых команд** - не нужна сложная инфраструктура

**Архитектурные улучшения:**

1. **Слоистая архитектура (Layered Architecture):**
   - **Presentation Layer** - Django REST API endpoints
   - **Application Layer** - Application Services, Use Cases
   - **Domain Layer** - Агрегаты, Entities, Value Objects, Domain Services
   - **Infrastructure Layer** - Repositories, External integrations

2. **Модульная структура:**
   - Каждый контекст = отдельное Django приложение
   - Четкие границы между модулями
   - Коммуникация через хорошо определенные интерфейсы

3. **Асинхронная обработка:**
   - Celery для фоновых задач
   - Redis как брокер сообщений
   - Асинхронная генерация отчетов

4. **Кэширование:**
   - Redis для кэширования справочников
   - Кэширование прав доступа
   - Оптимизация частых запросов

### 5. Визуализация целевой архитектуры — диаграмма С4

**Диаграмма контекста (Context)**

Диаграмма показывает систему "Расход Организации" в её окружении, включая всех пользователей и внешние системы, с которыми она взаимодействует.

![C4 Context Diagram](./schemas/c4-context/C4_Context_Diagram.png)

**Описание взаимодействий:**

1. **Пользователи → Система:**
   - Все пользователи взаимодействуют с системой через веб-интерфейс по HTTP/HTTPS
   - Каждая роль имеет свой набор доступных операций согласно матрице прав
   - Система предоставляет real-time обновления через WebSocket

2. **Система → Внешняя авторизация:**
   - Система получает JWT-токен от фронтенда
   - Валидирует подпись и срок действия токена
   - Извлекает информацию о роли и подразделении пользователя
   - Проверяет права доступа согласно матрице RBAC

3. **Система → Email сервер:**
   - Отправка уведомлений о критичных изменениях
   - Информирование об истечении отпусков/командировок
   - Оповещения о запросах на прикомандирование
   - Напоминания руководителям о необходимости одобрения

---

**Диаграмма контейнеров (Container)**

Диаграмма показывает высокоуровневую архитектуру монолитной системы с разделением на логические модули.

![C4 Container Diagram](./schemas/c4-container/C4_Container_Monolith.png)

**Основные контейнеры системы:**

1. **Frontend (Web Application):**
   - SPA приложение на React/Vue.js
   - Взаимодействует с backend через REST API
   - Получает real-time обновления через WebSocket (Django Channels)

2. **Django Monolith Application:**
   - Единое Django приложение с модульной структурой
   - Django REST Framework для API
   - Django Channels для WebSocket
   - Разделение на Django Apps по контекстам:
     - **divisions** - управление организационной структурой
     - **employees** - управление сотрудниками и штатным расписанием
     - **statuses** - управление статусами сотрудников
     - **secondments** - прикомандирование/откомандирование
     - **reports** - генерация отчетов (API endpoints)
     - **notifications** - WebSocket и email уведомления
     - **auth** - управление пользователями и правами
     - **audit** - журналирование всех операций
     - **dictionaries** - справочники

3. **Celery Workers:**
   - Асинхронная обработка задач генерации отчетов
   - Фоновые задачи (напоминания, очистка)
   - Масштабируются независимо от основного приложения

4. **База данных:**
   - **PostgreSQL** - единая БД для всего приложения
   - Схема разделена логически по модулям
   - Миграции управляются Django

5. **Вспомогательные компоненты:**
   - **Redis** - кэширование данных, брокер для Celery, WebSocket
   - **File Storage (S3/Local)** - хранение фотографий и отчетов
   - **Nginx** - веб-сервер, проксирование, статика

---

**Диаграмма компонентов (Component)**

Детальная структура Django приложения с разделением на слои согласно DDD подходу.

**Employee App - Управление сотрудниками:**

![C4 Component Diagram - Employee App](./schemas/c4-components/C4_Components_EmployeeApp.png)

**Структура Employee Django App:**

```
employees/
├── api/                          # API Layer (Presentation)
│   ├── views.py                  # ViewSets для REST API
│   ├── serializers.py            # DRF Serializers
│   └── permissions.py            # Permission classes
│
├── application/                  # Application Layer
│   ├── services.py               # Application Services
│   │   ├── EmployeeApplicationService
│   │   ├── PositionApplicationService
│   │   └── StaffingApplicationService
│   └── commands.py               # Command handlers
│
├── domain/                       # Domain Layer
│   ├── models/                   # Domain Models (Aggregates)
│   │   ├── employee.py           # Employee Aggregate
│   │   ├── position.py           # Position Aggregate
│   │   └── vacancy.py            # Vacancy Aggregate
│   ├── value_objects/            # Value Objects
│   │   ├── full_name.py
│   │   ├── photo.py
│   │   └── employment_period.py
│   ├── services.py               # Domain Services
│   └── events.py                 # Domain Events
│
├── infrastructure/               # Infrastructure Layer
│   ├── repositories.py           # Repository implementations
│   ├── event_publisher.py        # Event publishing
│   └── file_storage.py           # File operations
│
└── models.py                     # Django ORM Models (Persistence)
```

**Поток обработки запроса "Прием сотрудника на работу":**

1. HTTP Request → API View (JWT валидация через middleware)
2. API View → Permission Check (проверка прав Роль-4 или Роль-5)
3. API View → Employee Application Service
4. Employee Application Service → Division Service (проверка подразделения - вызов через Django)
5. Employee Application Service → Employee Domain (создание агрегата)
6. Employee Application Service → Employee Repository (сохранение в БД через Django ORM)
7. Employee Application Service → File Storage (загрузка фото в S3/Local)
8. Employee Application Service → Domain Event Publisher (событие `employee.created`)
9. Event Handler → Audit Service (логирование операции - вызов через Django)
10. Event Handler → Notification Service (уведомления - вызов через Django)

---

**Report Module - Генерация отчетов:**

![C4 Component Diagram - Report Module](./schemas/c4-components/C4_Components_ReportModule.png)

**Структура Report Django App:**

```
reports/
├── api/                          # API Layer
│   ├── views.py                  # API endpoints
│   └── serializers.py            # Serializers
│
├── application/                  # Application Layer
│   ├── services.py               # Report Application Service
│   └── job_service.py            # Job management
│
├── domain/                       # Domain Layer
│   ├── models/                   # Domain Models
│   │   ├── report.py
│   │   └── report_template.py
│   └── services.py               # Domain Services
│
├── infrastructure/               # Infrastructure Layer
│   ├── generators/               # Report Generators
│   │   ├── docx_generator.py    # python-docx
│   │   ├── xlsx_generator.py    # openpyxl
│   │   └── pdf_generator.py     # reportlab
│   ├── data_aggregator.py       # Data collection
│   └── storage.py                # File storage
│
├── tasks.py                      # Celery tasks
└── models.py                     # Django ORM Models
```

**Асинхронный поток генерации отчета:**

```
1. Пользователь → API: POST /api/reports/generate
2. API View → Report Service: создать задачу
3. Report Service → Пользователь: 202 Accepted {"job_id": "abc-123"}
4. Report Service → Celery: отправка задачи (через Redis)
5. Celery Worker → принимает задачу из очереди
6. Celery Worker → Data Aggregator: собрать данные
7. Data Aggregator → Django ORM: запросы к employees, statuses, divisions
8. Celery Worker → Generator (DOCX/XLSX/PDF): генерация файла
9. Celery Worker → File Storage (S3): сохранение отчета
10. Celery Worker → Django ORM: обновление статуса "completed"
11. Celery Worker → WebSocket (через Channels): "Отчет готов!"
12. Пользователь → API: GET /api/reports/{job_id}/download
```

**Преимущества асинхронной архитектуры:**

✅ Пользователь не ждет генерации (моментальный ответ)
✅ Можно масштабировать количество Celery Workers
✅ Отказоустойчивость - если worker упал, задача переназначится
✅ Приоритизация задач в очереди
✅ Таймауты не влияют на пользователя

---

**Диаграмма кода (Code)**

Детальные sequence и class диаграммы, показывающие реализацию ключевых use cases и доменной модели.

**Sequence диаграмма: Изменение статуса сотрудника**

![Status Change Sequence](./schemas/c4-code/Status_Change_Sequence_Monolith.png)

Диаграмма показывает полный процесс изменения статуса сотрудника с проверкой прав согласно RBAC матрице:

**Ключевые этапы проверки прав:**

1. **Валидация JWT токена** в Django middleware
2. **Извлечение контекста пользователя** (роль, подразделение) из токена
3. **Проверка прав на операцию** через Permission класс
4. **Проверка принадлежности сотрудника** - находится ли сотрудник в подразделении пользователя?
5. **Проверка иерархии подразделений** - вызов Division Service (тот же процесс Django)
6. **Проверка статуса пользователя** - не откомандирован ли пользователь?
7. **Валидация бизнес-правил** - нет пересечений периодов статусов (Domain Service)

**События после успешного изменения:**

- Django Signals → Audit Service (логирование операции)
- Django Signals → Notification Service (уведомления заинтересованным лицам)

---

**Sequence диаграмма: Прикомандирование сотрудника**

![Secondment Request Sequence](./schemas/c4-code/Secondment_Request_Sequence_Monolith.png)

Диаграмма показывает workflow прикомандирования с согласованием:

**Фаза 1: Запрос на прикомандирование**

1. Начальник управления А отправляет запрос через API
2. API View → Permission Check - может ли Роль-3 откомандировать сотрудника?
3. Secondment Application Service → проверка принадлежности к управлению А
4. Создание `SecondmentRequest` со статусом `pending_approval`
5. Django Signal → Notification Service (уведомление начальника управления Б)

**Фаза 2: Одобрение запроса**

1. Начальник управления Б получает уведомление (WebSocket + Email)
2. Просматривает детали запроса через API
3. Одобряет прикомандирование (POST /api/secondments/{id}/approve)
4. Проверка прав - управление Б является принимающей стороной?
5. Обновление статуса запроса на `approved`
6. Автоматическое изменение статуса сотрудника на "Прикомандирован"
7. Django Signals → Audit + Notification Services
8. Уведомления через WebSocket всем заинтересованным лицам

**Важные бизнес-правила:**

- Только начальник управления может откомандировать своего сотрудника (Роль-3)
- Требуется одобрение принимающей стороны
- После прикомандирования сотрудник может получать дополнительные статусы в новом подразделении
- Исходное управление не теряет сотрудника из штата

---

**Class диаграмма: Доменная модель Employee Module**

![Employee Domain Model](./schemas/c4-code/Employee_Domain_Model_Class.png)

Диаграмма показывает структуру доменной модели согласно принципам DDD:

**Агрегаты (Aggregate Roots):**

1. **Employee** - корневая сущность сотрудника
   - Контролирует жизненный цикл: прием, перевод, увольнение
   - Публикует domain events: `EmployeeHired`, `EmployeeTransferred`, `EmployeeFired`
   - Инварианты: сотрудник всегда привязан к подразделению и должности

2. **PositionAssignment** - назначение на должность
   - Поддерживает постоянные и временные назначения
   - Назначение "за счёт" другой должности (`substitute_for_position_id`)
   - Исполнение обязанностей (Acting)

3. **Vacancy** - вакантная должность
   - Управляет жизненным циклом вакансии
   - Статусы: OPEN, FILLED, CLOSED, CANCELLED
   - Может быть заполнена конкретным сотрудником

**Value Objects (объекты-значения):**

- `FullName` - ФИО сотрудника (неизменяемый)
- `Photo` - метаданные фотографии
- `EmploymentPeriod` - период работы (дата приема, дата увольнения)
- `Rank` - звание/ранг сотрудника

**Entities (сущности):**

- `Position` - должность из справочника
- `StaffingTableEntry` - запись в штатном расписании

**Domain Events:**

События, которые публикуются при изменении состояния агрегатов (через Django Signals):
- `EmployeeHired` - прием на работу
- `EmployeeTransferred` - перевод на другую должность/подразделение
- `EmployeeFired` - увольнение
- `VacancyCreated` - создание вакансии
- `VacancyFilled` - заполнение вакансии

**Принципы DDD в монолите:**

✅ **Агрегаты** - четкие границы транзакционной целостности
✅ **Value Objects** - неизменяемые объекты для концептуальной целостности
✅ **Domain Events** - явное моделирование важных бизнес-событий (через Django Signals)
✅ **Invariants** - бизнес-правила инкапсулированы в агрегатах
✅ **Ubiquitous Language** - названия из предметной области бизнеса
✅ **Layered Architecture** - четкое разделение слоев внутри Django Apps

---

## Технический стек целевой системы

**Backend:**
- Python 3.11+
- Django 5.0+
- Django REST Framework 3.14+
- Django Channels 4.0+ (WebSocket)
- Celery 5.3+ (асинхронные задачи)
- python-docx (генерация Word)
- openpyxl (генерация Excel)
- reportlab (генерация PDF)

**Database:**
- PostgreSQL 15+

**Cache & Message Broker:**
- Redis 7.0+

**Frontend:**
- React 18+ или Vue.js 3+
- WebSocket клиент

**Infrastructure:**
- Docker & Docker Compose
- Nginx
- Gunicorn
- AWS S3 или MinIO (файловое хранилище)

---

## Структура проекта

```
organization_management/
├── config/                          # Настройки Django проекта
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
│
├── apps/                            # Django приложения
│   ├── divisions/                   # Организационная структура
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   └── models.py
│   │
│   ├── employees/                   # Управление сотрудниками
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   └── models.py
│   │
│   ├── statuses/                    # Статусы сотрудников
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   └── models.py
│   │
│   ├── secondments/                 # Прикомандирование
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   └── models.py
│   │
│   ├── reports/                     # Генерация отчетов
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   ├── tasks.py                # Celery tasks
│   │   └── models.py
│   │
│   ├── notifications/               # Уведомления
│   │   ├── api/
│   │   ├── consumers.py            # WebSocket consumers
│   │   ├── services.py
│   │   └── models.py
│   │
│   ├── auth/                        # Аутентификация и авторизация
│   │   ├── api/
│   │   ├── middleware/
│   │   ├── permissions.py
│   │   └── models.py
│   │
│   ├── audit/                       # Журнал аудита
│   │   ├── api/
│   │   ├── services.py
│   │   └── models.py
│   │
│   └── dictionaries/                # Справочники
│       ├── api/
│       ├── services.py
│       └── models.py
│
├── common/                          # Общие компоненты
│   ├── exceptions.py
│   ├── pagination.py
│   ├── permissions.py
│   └── utils.py
│
├── tests/                           # Тесты
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
│
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
│
└── manage.py
```

---

## Преимущества монолитной архитектуры с DDD

**1. Транзакционная целостность:**
- Все операции в одной БД
- ACID транзакции из коробки
- Нет проблем с распределенными транзакциями

**2. Простота разработки:**
- Один проект, одна кодовая база
- Простая отладка
- Быстрый старт разработки

**3. Простота развертывания:**
- Один Docker контейнер
- Простой CI/CD pipeline
- Меньше инфраструктурной сложности

**4. Производительность:**
- Нет сетевых вызовов между модулями
- Быстрый доступ к данным
- Эффективные JOIN-ы в БД

**5. Модульность внутри монолита:**
- Четкие границы между Django Apps
- DDD паттерны для управления сложностью
- Возможность будущего разделения на микросервисы

**6. Меньше накладных расходов:**
- Одна БД для управления
- Одна система логирования
- Единая система мониторинга

---

## Масштабирование монолита

**Вертикальное масштабирование:**
- Увеличение CPU/RAM сервера
- Подходит для нагрузки до 5000 сотрудников

**Горизонтальное масштабирование:**
- Несколько экземпляров Django за Load Balancer
- Celery workers масштабируются независимо
- Shared PostgreSQL и Redis

**Оптимизация:**
- Кэширование в Redis
- Database connection pooling (pgbouncer)
- Индексы в PostgreSQL
- Асинхронная обработка тяжелых операций

---

## Путь миграции к микросервисам (будущее)

Если в будущем понадобится переход к микросервисам:

1. **Границы уже определены** - каждое Django приложение может стать отдельным сервисом
2. **DDD паттерны** - упрощают выделение bounded contexts
3. **Слоистая архитектура** - минимизирует изменения при выделении
4. **События через Signals** - легко заменить на message broker
5. **Repository паттерн** - изолирует работу с БД

**Приоритет выделения:**
1. Report Service (самый ресурсоемкий)
2. Notification Service (независимый)
3. Audit Service (независимый)

---

## Заключение

Монолитная архитектура с применением DDD паттернов и модульной структурой предоставляет:

✅ Простоту разработки и поддержки для малой команды
✅ Высокую производительность для целевой нагрузки
✅ Транзакционную целостность данных
✅ Возможность будущей миграции к микросервисам
✅ Четкую структуру и управляемую сложность

Данная архитектура оптимальна для системы с 500 пользователями и 5000 сотрудников, обеспечивая баланс между простотой и масштабируемостью.
