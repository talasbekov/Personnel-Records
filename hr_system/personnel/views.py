"""
ViewSets и API endpoints для управления организационной структурой и персоналом.

Полная реализация всех требований технического задания, включая:
- Управление организационной структурой с поддержкой трех вариантов иерархии
- Массовое обновление статусов сотрудников
- Генерация отчетов в форматах DOCX, XLSX, PDF
- Система прикомандирования/откомандирования
- Управление штатным расписанием и вакансиями
- Индикаторы обновления статусов
- Экспорт/импорт структуры организации
"""

import io
import csv
import datetime

from django.http import HttpResponse
from django.db import transaction
from django.db.models import Count, Q, F, Prefetch
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.exceptions import ValidationError

from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    Division, Position, Employee, UserProfile, SecondmentRequest,
    EmployeeStatusLog, StaffingUnit, Vacancy, DivisionStatusUpdate,
    PersonnelReport, EmployeeTransferLog, UserRole,
    DivisionType, SecondmentStatus, ReportType
)
from .serializers import (
    DivisionSerializer, DivisionDetailSerializer, DivisionTreeSerializer,
    PositionSerializer, EmployeeSerializer, EmployeeDetailSerializer,
    UserProfileSerializer, SecondmentRequestSerializer,
    EmployeeStatusLogSerializer, StaffingUnitSerializer,
    VacancySerializer, PersonnelReportSerializer,
    EmployeeTransferLogSerializer, BulkStatusUpdateSerializer,
    EmployeeStatusSerializer
)
from .permissions import (
    IsRole1, IsRole2, IsRole3, IsRole4, IsRole5, IsRole6,
    IsReadOnly
)
from .throttles import (
    ReportGenerationThrottle, AuthRateThrottle, RoleRateThrottle
)
from .services import (
    generate_personnel_report_docx, generate_personnel_report_xlsx,
    generate_personnel_report_pdf, get_division_statistics
)
from notifications.models import Notification, NotificationType
from audit.models import AuditLog


# Helper функции для работы с иерархией подразделений
def _gather_descendant_ids(division):
    """Рекурсивно собрать ID всех потомков подразделения"""
    ids = [division.id]
    for child in division.child_divisions.all():
        ids.extend(_gather_descendant_ids(child))
    return ids


def _build_division_tree(division, include_employees=False):
    """Построить дерево подразделений с опциональным включением сотрудников"""
    data = {
        'id': division.id,
        'name': division.name,
        'code': division.code,
        'division_type': division.division_type,
        'division_type_display': division.get_division_type_display(),
        'children': []
    }

    if include_employees:
        employees = division.employees.filter(is_active=True).select_related('position')
        data['employees'] = [
            {
                'id': emp.id,
                'full_name': emp.full_name,
                'position': emp.position.name,
                'position_level': emp.position.level,
                'current_status': emp.get_current_status()
            }
            for emp in employees.order_by('position__level', 'full_name')
        ]

    for child in division.child_divisions.all().order_by('division_type', 'name'):
        data['children'].append(_build_division_tree(child, include_employees))

    return data


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Расширенный сериализатор для JWT токенов с информацией о роли"""

    def validate(self, attrs):
        data = super().validate(attrs)

        try:
            profile = self.user.profile
            data['role'] = profile.role
            data['role_display'] = UserRole(profile.role).label
            data['division_id'] = profile.division_assignment.id if profile.division_assignment else None
            data['division_name'] = profile.division_assignment.name if profile.division_assignment else None

            # Добавляем информацию о сотруднике, если есть связь
            try:
                employee = self.user.employee
                data['employee_id'] = employee.id
                data['employee_name'] = employee.full_name
            except Employee.DoesNotExist:
                data['employee_id'] = None
                data['employee_name'] = None

        except Exception:
            data['role'] = None
            data['role_display'] = None
            data['division_id'] = None
            data['division_name'] = None

        return data


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    throttle_classes = [AuthRateThrottle]


class DivisionViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления подразделениями организации.

    Поддерживает все CRUD операции, а также дополнительные действия:
    - Массовый импорт/экспорт структуры
    - Перемещение подразделений в иерархии
    - Генерация отчетов
    - Обновление статусов сотрудников
    """
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'division_type', 'created_at']
    ordering = ['division_type', 'name']
    throttle_classes = [RoleRateThrottle]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DivisionDetailSerializer
        elif self.action == 'tree':
            return DivisionTreeSerializer
        return self.serializer_class

    def get_permissions(self):
        """
        Раздаём permissions в зависимости от действия.
        CSV-экспорт вынесён в отдельный @action export().
        """
        if self.action in ['list', 'retrieve', 'tree', 'status_summary', 'export']:
            permission_classes = [IsAuthenticated, IsReadOnly | IsRole4 | IsRole5]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'move', 'bulk_import']:
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        elif self.action in ['update_statuses', 'report', 'periodic_report']:
            permission_classes = [IsAuthenticated, IsRole3 | IsRole4 | IsRole5 | IsRole6]
        else:
            # По умолчанию — любому аутентифированному
            permission_classes = [IsAuthenticated]
        return [perm() for perm in permission_classes]

    @action(detail=True, methods=['post'])
    @swagger_auto_schema(
        request_body=BulkStatusUpdateSerializer(many=True)
    )
    def update_statuses(self, request, pk=None):
        """
        Массовое обновление статусов сотрудников подразделения.

        Body: список объектов с полями:
        - employee_id: int
        - status: str
        - date_from: date
        - date_to: date (optional)
        - comment: str (optional)
        """
        division = self.get_object()
        user = request.user

        # Проверка прав на редактирование
        if not self._can_edit_division_statuses(user, division):
            return Response(
                {'error': 'Недостаточно прав для редактирования статусов'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BulkStatusUpdateSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        created_logs = []
        errors = []

        with transaction.atomic():
            for item in serializer.validated_data:
                try:
                    employee = Employee.objects.get(
                        id=item['employee_id'],
                        division=division,
                        is_active=True
                    )

                    # Создаем запись в журнале статусов
                    log = EmployeeStatusLog.objects.create(
                        employee=employee,
                        status=item['status'],
                        date_from=item['date_from'],
                        date_to=item.get('date_to'),
                        comment=item.get('comment', ''),
                        created_by=user
                    )
                    created_logs.append(log)

                except Employee.DoesNotExist:
                    errors.append(f"Сотрудник с ID {item['employee_id']} не найден")
                except ValidationError as e:
                    errors.append(f"Ошибка для сотрудника {item['employee_id']}: {str(e)}")

            # Обновляем индикатор статуса подразделения
            today = timezone.now().date()
            status_update, created = DivisionStatusUpdate.objects.get_or_create(
                division=division,
                update_date=today,
                defaults={'is_updated': True, 'updated_by': user}
            )
            if not created:
                status_update.mark_as_updated(user)

            # Проверяем и обновляем статус родительского подразделения
            self._update_parent_division_status(division, today, user)

        # Создаем уведомления
        if created_logs:
            self._create_status_update_notifications(division, user)

        return Response({
            'created': len(created_logs),
            'errors': errors
        }, status=status.HTTP_201_CREATED if created_logs else status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def status_summary(self, request):
        """
        Получить сводку по статусам обновления всех подразделений.

        Query parameters:
        - date: date - дата для проверки (по умолчанию сегодня)
        """
        date_str = request.query_params.get('date')
        try:
            check_date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем все доступные подразделения
        divisions = self.get_queryset()

        # Собираем информацию о статусах
        result = []
        for division in divisions:
            # Статус самого подразделения
            status_update = DivisionStatusUpdate.objects.filter(
                division=division,
                update_date=check_date
            ).first()

            div_data = {
                'id': division.id,
                'name': division.name,
                'division_type': division.division_type,
                'is_updated': status_update.is_updated if status_update else False,
                'updated_at': status_update.updated_at if status_update else None,
                'indicator': 'GREEN' if status_update and status_update.is_updated else 'RED'
            }

            # Для департаментов проверяем дочерние управления
            if division.division_type == DivisionType.DEPARTMENT:
                child_statuses = []
                for child in division.child_divisions.filter(division_type=DivisionType.MANAGEMENT):
                    child_update = DivisionStatusUpdate.objects.filter(
                        division=child,
                        update_date=check_date
                    ).first()
                    child_statuses.append({
                        'id': child.id,
                        'name': child.name,
                        'is_updated': child_update.is_updated if child_update else False,
                        'indicator': 'GREEN' if child_update and child_update.is_updated else 'RED'
                    })

                # Определяем общий индикатор департамента
                if child_statuses:
                    updated_count = sum(1 for cs in child_statuses if cs['is_updated'])
                    total_count = len(child_statuses)

                    if updated_count == total_count:
                        div_data['indicator'] = 'GREEN'
                    elif updated_count > 0:
                        div_data['indicator'] = 'YELLOW'
                    else:
                        div_data['indicator'] = 'RED'

                    div_data['children'] = child_statuses
                    div_data['updated_children'] = updated_count
                    div_data['total_children'] = total_count

            result.append(div_data)

        return Response(result)

    @action(detail=True, methods=['get'])
    @method_decorator(cache_page(60 * 15))  # Кэш на 15 минут
    def statistics(self, request, pk=None):
        """
        Получить статистику по подразделению.

        Query parameters:
        - date: date - дата для расчета (по умолчанию сегодня)
        """
        division = self.get_object()
        date_str = request.query_params.get('date')

        try:
            calc_date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stats = get_division_statistics(division, calc_date)
        return Response(stats)

    @action(detail=True, methods=['get'], throttle_classes=[ReportGenerationThrottle])
    def report(self, request, pk=None):
        """
        Генерация отчета расхода личного состава.

        Query parameters:
        - date: date - дата отчета (по умолчанию завтра)
        - format: str - формат файла (docx, xlsx, pdf)
        """
        division = self.get_object()

        # Парсинг параметров
        date_str = request.query_params.get('date')
        if date_str:
            try:
                report_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return Response(
                    {'error': 'Неверный формат даты'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # По умолчанию - завтрашняя дата
            report_date = timezone.now().date() + datetime.timedelta(days=1)

        file_format = request.query_params.get('format', 'docx').lower()

        # Проверка, что все подразделения обновили статусы
        if not self._check_all_statuses_updated(division, report_date - datetime.timedelta(days=1)):
            return Response(
                {'error': 'Не все подразделения обновили статусы. Генерация отчета невозможна.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Генерация отчета
            if file_format == 'xlsx':
                file_buffer = generate_personnel_report_xlsx(division, report_date)
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                filename = f'personnel_report_{division.code}_{report_date}.xlsx'
            elif file_format == 'pdf':
                file_buffer = generate_personnel_report_pdf(division, report_date)
                content_type = 'application/pdf'
                filename = f'personnel_report_{division.code}_{report_date}.pdf'
            else:  # docx
                file_buffer = generate_personnel_report_docx(division, report_date)
                content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                filename = f'personnel_report_{division.code}_{report_date}.docx'

            # Сохранение отчета в БД
            report = PersonnelReport.objects.create(
                division=division,
                report_date=report_date,
                report_type=ReportType.DAILY,
                date_from=report_date,
                date_to=report_date,
                file_format=file_format,
                created_by=request.user
            )
            report.file.save(filename, file_buffer)

            # Создание записи в аудите
            AuditLog.objects.create(
                user=request.user,
                action_type='REPORT_GENERATED',
                payload={
                    'division_id': division.id,
                    'report_date': str(report_date),
                    'format': file_format
                }
            )

            # Отправка файла
            response = HttpResponse(
                file_buffer.getvalue(),
                content_type=content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return Response(
                {'error': f'Ошибка генерации отчета: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], throttle_classes=[ReportGenerationThrottle])
    def periodic_report(self, request, pk=None):
        """
        Генерация отчета за период.

        Query parameters:
        - date_from: date - начальная дата
        - date_to: date - конечная дата
        - format: str - формат файла (docx, xlsx, pdf)
        """
        division = self.get_object()

        # Парсинг дат
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')

        if not date_from_str or not date_to_str:
            return Response(
                {'error': 'Необходимо указать date_from и date_to'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            date_from = datetime.date.fromisoformat(date_from_str)
            date_to = datetime.date.fromisoformat(date_to_str)
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if date_from > date_to:
            return Response(
                {'error': 'date_from не может быть больше date_to'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ограничение на длину периода
        if (date_to - date_from).days > 31:
            return Response(
                {'error': 'Максимальный период - 31 день'},
                status=status.HTTP_400_BAD_REQUEST
            )

        file_format = request.query_params.get('format', 'docx').lower()

        try:
            # Генерация мультистраничного отчета
            if file_format == 'xlsx':
                file_buffer = generate_personnel_report_xlsx(
                    division, date_from, date_to
                )
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif file_format == 'pdf':
                file_buffer = generate_personnel_report_pdf(
                    division, date_from, date_to
                )
                content_type = 'application/pdf'
            else:
                file_buffer = generate_personnel_report_docx(
                    division, date_from, date_to
                )
                content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

            filename = f'personnel_report_{division.code}_{date_from}_{date_to}.{file_format}'

            # Сохранение отчета
            report = PersonnelReport.objects.create(
                division=division,
                report_date=date_from,
                report_type=ReportType.PERIOD,
                date_from=date_from,
                date_to=date_to,
                file_format=file_format,
                created_by=request.user
            )
            report.file.save(filename, file_buffer)

            response = HttpResponse(
                file_buffer.getvalue(),
                content_type=content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return Response(
                {'error': f'Ошибка генерации отчета: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Вспомогательные методы
    def _can_edit_division_statuses(self, user, division):
        """Проверка прав на редактирование статусов подразделения"""
        if not hasattr(user, 'profile'):
            return False

        profile = user.profile

        # Роль 4 может редактировать все
        if profile.role == UserRole.ROLE_4:
            return True

        # Роли 3 и 6 могут редактировать только свое подразделение
        if profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]:
            # Проверка, что пользователь не откомандирован
            try:
                employee = user.employee
                if employee.is_seconded_out():
                    return False
            except Employee.DoesNotExist:
                pass

            return profile.division_assignment == division

        # Роль 5 может редактировать в рамках своего назначения
        if profile.role == UserRole.ROLE_5:
            return profile.has_access_to_division(division)

        return False

    def _update_parent_division_status(self, division, date, user):
        """Обновление статуса родительского департамента"""
        if division.division_type != DivisionType.MANAGEMENT:
            return

        parent = division.parent_division
        if not parent or parent.division_type != DivisionType.DEPARTMENT:
            return

        # Проверяем все управления в департаменте
        managements = parent.child_divisions.filter(division_type=DivisionType.MANAGEMENT)
        all_updated = True

        for mgmt in managements:
            status = DivisionStatusUpdate.objects.filter(
                division=mgmt,
                update_date=date
            ).first()
            if not status or not status.is_updated:
                all_updated = False
                break

        # Обновляем статус департамента
        dept_status, created = DivisionStatusUpdate.objects.get_or_create(
            division=parent,
            update_date=date,
            defaults={'is_updated': all_updated, 'updated_by': user if all_updated else None}
        )
        if not created and all_updated:
            dept_status.mark_as_updated(user)

    def _check_all_statuses_updated(self, division, date):
        """Проверка, что все подразделения обновили статусы"""
        if division.division_type == DivisionType.DEPARTMENT:
            # Для департамента проверяем все управления
            managements = division.child_divisions.filter(division_type=DivisionType.MANAGEMENT)
            for mgmt in managements:
                status = DivisionStatusUpdate.objects.filter(
                    division=mgmt,
                    update_date=date
                ).first()
                if not status or not status.is_updated:
                    return False
        else:
            # Для других типов проверяем само подразделение
            status = DivisionStatusUpdate.objects.filter(
                division=division,
                update_date=date
            ).first()
            if not status or not status.is_updated:
                return False

        return True

    def _create_status_update_notifications(self, division, user):
        """Создание уведомлений об обновлении статусов"""
        # Уведомляем начальника департамента
        if division.division_type == DivisionType.MANAGEMENT:
            parent = division.parent_division
            if parent and parent.division_type == DivisionType.DEPARTMENT:
                dept_heads = UserProfile.objects.filter(
                    role=UserRole.ROLE_2,
                    division_assignment=parent
                )
                for profile in dept_heads:
                    Notification.objects.create(
                        recipient=profile.user,
                        notification_type=NotificationType.STATUS_UPDATE,
                        title=f'Обновлены статусы в {division.name}',
                        message=f'Пользователь {user.get_full_name()} обновил статусы сотрудников в управлении {division.name}',
                        related_object_id=division.id,
                        related_model='Division'
                    )


class PositionViewSet(viewsets.ModelViewSet):
    """ViewSet для управления должностями"""

    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['level', 'name']
    ordering = ['level']
    throttle_classes = [RoleRateThrottle]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        return [permission() for permission in permission_classes]

    @method_decorator(cache_page(60 * 60))  # Кэш на 1 час
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class EmployeeViewSet(viewsets.ModelViewSet):
    """ViewSet для управления сотрудниками"""

    serializer_class = EmployeeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['full_name', 'employee_number']
    ordering_fields = ['full_name', 'position__level', 'created_at']
    ordering = ['position__level', 'full_name']
    throttle_classes = [RoleRateThrottle]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmployeeDetailSerializer
        elif self.action in ['current_status', 'status_history']:
            return EmployeeStatusSerializer
        return self.serializer_class

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'current_status', 'status_history']:
            permission_classes = [IsAuthenticated]
        elif self.action in ['terminate', 'transfer']:
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        else:
            permission_classes = [IsAuthenticated, IsRole3 | IsRole4 | IsRole5 | IsRole6]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтрация сотрудников на основе роли пользователя"""
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            return Employee.objects.none()

        profile = user.profile
        queryset = Employee.objects.select_related(
            'division', 'position', 'user', 'acting_for_position'
        ).prefetch_related('status_logs')

        # Роли 1 и 4 видят всех
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return queryset

        # Остальные видят только сотрудников своих подразделений
        if not profile.division_assignment:
            return Employee.objects.none()

        if profile.role == UserRole.ROLE_2 or (
            profile.role == UserRole.ROLE_5 and profile.include_child_divisions
        ):
            descendant_ids = _gather_descendant_ids(profile.division_assignment)
            queryset = queryset.filter(division_id__in=descendant_ids)
        else:
            queryset = queryset.filter(division=profile.division_assignment)

        # Фильтр по активности
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Фильтр по подразделению
        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(division_id=division_id)

        # Фильтр по должности
        position_id = self.request.query_params.get('position_id')
        if position_id:
            queryset = queryset.filter(position_id=position_id)

        # Фильтр по текущему статусу
        current_status = self.request.query_params.get('current_status')
        if current_status:
            today = timezone.now().date()
            employee_ids = []
            for emp in queryset:
                if emp.get_current_status(today) == current_status:
                    employee_ids.append(emp.id)
            queryset = queryset.filter(id__in=employee_ids)

        return queryset

    def perform_create(self, serializer):
        """Автоматическое заполнение полей при создании"""
        employee = serializer.save()

        # Создаем запись в журнале переводов
        EmployeeTransferLog.objects.create(
            employee=employee,
            to_division=employee.division,
            to_position=employee.position,
            transfer_date=employee.hired_date or timezone.now().date(),
            reason='Прием на работу',
            created_by=self.request.user
        )

    @action(detail=True, methods=['get'])
    def current_status(self, request, pk=None):
        """
        Получить текущий статус сотрудника.

        Query parameters:
        - date: date - дата для проверки (по умолчанию сегодня)
        """
        employee = self.get_object()
        date_str = request.query_params.get('date')

        try:
            check_date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты'},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_details = employee.get_status_details(check_date)
        return Response(status_details)

    @action(detail=True, methods=['get'])
    def status_history(self, request, pk=None):
        """
        Получить историю статусов сотрудника.

        Query parameters:
        - date_from: date - начальная дата
        - date_to: date - конечная дата
        """
        employee = self.get_object()

        queryset = employee.status_logs.all()

        # Фильтрация по датам
        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_from__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(
                Q(date_to__lte=date_to) | Q(date_to__isnull=True)
            )

        serializer = EmployeeStatusLogSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """
        Уволить сотрудника.

        Body parameters:
        - fired_date: date - дата увольнения
        - reason: str - причина увольнения
        """
        employee = self.get_object()

        if not employee.is_active:
            return Response(
                {'error': 'Сотрудник уже уволен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        fired_date_str = request.data.get('fired_date')
        if fired_date_str:
            try:
                fired_date = datetime.date.fromisoformat(fired_date_str)
            except ValueError:
                return Response(
                    {'error': 'Неверный формат даты'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            fired_date = timezone.now().date()

        reason = request.data.get('reason', 'Увольнение по собственному желанию')

        # Обновляем сотрудника
        employee.is_active = False
        employee.fired_date = fired_date
        employee.save()

        # Закрываем активные статусы
        active_logs = employee.status_logs.filter(date_to__isnull=True)
        for log in active_logs:
            log.date_to = fired_date
            log.save()

        # Создаем запись в журнале переводов
        EmployeeTransferLog.objects.create(
            employee=employee,
            from_division=employee.division,
            from_position=employee.position,
            transfer_date=fired_date,
            reason=reason,
            created_by=request.user
        )

        serializer = self.get_serializer(employee)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """
        Перевести сотрудника в другое подразделение.

        Body parameters:
        - new_division_id: int
        - new_position_id: int (optional)
        - transfer_date: date
        - reason: str
        """
        employee = self.get_object()

        new_division_id = request.data.get('new_division_id')
        if not new_division_id:
            return Response(
                {'error': 'Необходимо указать new_division_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_division = Division.objects.get(pk=new_division_id)
        except Division.DoesNotExist:
            return Response(
                {'error': 'Подразделение не найдено'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверка прав на перевод в целевое подразделение
        user_profile = request.user.profile
        if user_profile.role == UserRole.ROLE_5:
            if not user_profile.has_access_to_division(new_division):
                return Response(
                    {'error': 'Недостаточно прав для перевода в указанное подразделение'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Получаем данные для перевода
        new_position_id = request.data.get('new_position_id')
        new_position = None
        if new_position_id:
            try:
                new_position = Position.objects.get(pk=new_position_id)
            except Position.DoesNotExist:
                return Response(
                    {'error': 'Должность не найдена'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            new_position = employee.position

        transfer_date_str = request.data.get('transfer_date')
        if transfer_date_str:
            try:
                transfer_date = datetime.date.fromisoformat(transfer_date_str)
            except ValueError:
                return Response(
                    {'error': 'Неверный формат даты'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            transfer_date = timezone.now().date()

        reason = request.data.get('reason', 'Перевод по производственной необходимости')

        # Сохраняем старые данные для журнала
        old_division = employee.division
        old_position = employee.position

        # Обновляем сотрудника
        employee.division = new_division
        employee.position = new_position
        employee.save()

        # Создаем запись в журнале переводов
        EmployeeTransferLog.objects.create(
            employee=employee,
            from_division=old_division,
            to_division=new_division,
            from_position=old_position,
            to_position=new_position,
            transfer_date=transfer_date,
            reason=reason,
            created_by=request.user
        )

        # Создаем уведомления
        if old_division != new_division:
            # Уведомляем руководителей обоих подразделений
            for division in [old_division, new_division]:
                managers = UserProfile.objects.filter(
                    Q(role=UserRole.ROLE_3, division_assignment=division) |
                    Q(role=UserRole.ROLE_2, division_assignment=division.parent_division)
                )
                for profile in managers:
                    Notification.objects.create(
                        recipient=profile.user,
                        notification_type=NotificationType.TRANSFER,
                        title=f'Перевод сотрудника {employee.full_name}',
                        message=f'Сотрудник {employee.full_name} переведен из {old_division.name} в {new_division.name}',
                        related_object_id=employee.id,
                        related_model='Employee'
                    )

        serializer = self.get_serializer(employee)
        return Response(serializer.data)


class EmployeeStatusLogViewSet(viewsets.ModelViewSet):
    """ViewSet для управления журналом статусов сотрудников"""

    queryset = EmployeeStatusLog.objects.all()
    serializer_class = EmployeeStatusLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_from', 'created_at']
    ordering = ['-date_from']
    throttle_classes = [RoleRateThrottle]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsRole3 | IsRole4 | IsRole5 | IsRole6]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтрация журнала на основе роли и параметров"""
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            return EmployeeStatusLog.objects.none()

        profile = user.profile
        queryset = EmployeeStatusLog.objects.select_related(
            'employee', 'employee__division', 'created_by', 'secondment_division'
        )

        # Фильтрация по роли
        if profile.role not in [UserRole.ROLE_1, UserRole.ROLE_4]:
            if not profile.division_assignment:
                return EmployeeStatusLog.objects.none()

            if profile.role == UserRole.ROLE_2 or (
                profile.role == UserRole.ROLE_5 and profile.include_child_divisions
            ):
                descendant_ids = _gather_descendant_ids(profile.division_assignment)
                queryset = queryset.filter(employee__division_id__in=descendant_ids)
            else:
                queryset = queryset.filter(employee__division=profile.division_assignment)

        # Фильтр по сотруднику
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        # Фильтр по статусу
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Фильтр по датам
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date_from__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(
                Q(date_to__lte=date_to) | Q(date_to__isnull=True)
            )

        # Фильтр по автокопированию
        is_auto_copied = self.request.query_params.get('is_auto_copied')
        if is_auto_copied is not None:
            queryset = queryset.filter(is_auto_copied=is_auto_copied.lower() == 'true')

        return queryset

    def perform_create(self, serializer):
        """Автоматическое заполнение полей при создании"""
        serializer.save(created_by=self.request.user)


class SecondmentRequestViewSet(viewsets.ModelViewSet):
    """ViewSet для управления запросами на прикомандирование"""

    queryset = SecondmentRequest.objects.all()
    serializer_class = SecondmentRequestSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'date_from', 'status']
    ordering = ['-created_at']
    throttle_classes = [RoleRateThrottle]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        elif self.action in ['approve', 'reject', 'request_return', 'approve_return']:
            permission_classes = [IsAuthenticated, IsRole3 | IsRole4 | IsRole5]
        else:
            permission_classes = [IsAuthenticated, IsRole3 | IsRole4 | IsRole5]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтрация запросов на основе роли"""
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            return SecondmentRequest.objects.none()

        profile = user.profile
        queryset = SecondmentRequest.objects.select_related(
            'employee', 'from_division', 'to_division',
            'requested_by', 'approved_by'
        )

        # Роли 1 и 4 видят все
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return queryset

        # Остальные видят только запросы своих подразделений
        if not profile.division_assignment:
            return SecondmentRequest.objects.none()

        if profile.role == UserRole.ROLE_2:
            descendant_ids = _gather_descendant_ids(profile.division_assignment)
            queryset = queryset.filter(
                Q(from_division_id__in=descendant_ids) |
                Q(to_division_id__in=descendant_ids)
            )
        elif profile.role == UserRole.ROLE_5:
            if profile.include_child_divisions:
                descendant_ids = _gather_descendant_ids(profile.division_assignment)
                queryset = queryset.filter(
                    Q(from_division_id__in=descendant_ids) |
                    Q(to_division_id__in=descendant_ids)
                )
            else:
                queryset = queryset.filter(
                    Q(from_division=profile.division_assignment) |
                    Q(to_division=profile.division_assignment)
                )
        else:  # ROLE_3, ROLE_6
            queryset = queryset.filter(
                Q(from_division=profile.division_assignment) |
                Q(to_division=profile.division_assignment)
            )

        # Фильтры
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        return queryset

    def perform_create(self, serializer):
        """Автоматическое заполнение полей при создании"""
        serializer.save(requested_by=self.request.user)

        # Создаем уведомления
        instance = serializer.instance

        # Уведомляем начальника принимающего подразделения
        managers = UserProfile.objects.filter(
            role__in=[UserRole.ROLE_3, UserRole.ROLE_2],
            division_assignment=instance.to_division
        )
        for profile in managers:
            Notification.objects.create(
                recipient=profile.user,
                notification_type=NotificationType.SECONDMENT,
                title=f'Запрос на прикомандирование {instance.employee.full_name}',
                message=f'Получен запрос на прикомандирование сотрудника {instance.employee.full_name} из {instance.from_division.name}',
                related_object_id=instance.id,
                related_model='SecondmentRequest'
            )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Одобрить запрос на прикомандирование"""
        secondment = self.get_object()

        if secondment.status != SecondmentStatus.PENDING:
            return Response(
                {'error': 'Запрос уже обработан'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка прав
        user_profile = request.user.profile
        if user_profile.role not in [UserRole.ROLE_4]:
            if not user_profile.has_access_to_division(secondment.to_division):
                return Response(
                    {'error': 'Недостаточно прав для одобрения'},
                    status=status.HTTP_403_FORBIDDEN
                )

        secondment.approve(request.user)

        # Создаем уведомления
        Notification.objects.create(
            recipient=secondment.requested_by,
            notification_type=NotificationType.SECONDMENT,
            title=f'Запрос на прикомандирование одобрен',
            message=f'Запрос на прикомандирование {secondment.employee.full_name} в {secondment.to_division.name} одобрен',
            related_object_id=secondment.id,
            related_model='SecondmentRequest'
        )

        serializer = self.get_serializer(secondment)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Отклонить запрос на прикомандирование"""
        secondment = self.get_object()

        if secondment.status != SecondmentStatus.PENDING:
            return Response(
                {'error': 'Запрос уже обработан'},
                status=status.HTTP_400_BAD_REQUEST
            )

        secondment.reject(request.user)

        # Создаем уведомления
        Notification.objects.create(
            recipient=secondment.requested_by,
            notification_type=NotificationType.SECONDMENT,
            title=f'Запрос на прикомандирование отклонен',
            message=f'Запрос на прикомандирование {secondment.employee.full_name} в {secondment.to_division.name} отклонен',
            related_object_id=secondment.id,
            related_model='SecondmentRequest'
        )

        serializer = self.get_serializer(secondment)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def request_return(self, request, pk=None):
        """Запросить возврат сотрудника"""
        secondment = self.get_object()

        if secondment.status != SecondmentStatus.APPROVED:
            return Response(
                {'error': 'Можно запросить возврат только для одобренных запросов'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if secondment.return_requested:
            return Response(
                {'error': 'Возврат уже запрошен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        secondment.request_return(request.user)

        # Создаем уведомления
        managers = UserProfile.objects.filter(
            role__in=[UserRole.ROLE_3, UserRole.ROLE_2],
            division_assignment=secondment.to_division
        )
        for profile in managers:
            Notification.objects.create(
                recipient=profile.user,
                notification_type=NotificationType.RETURN_REQUEST,
                title=f'Запрос на возврат {secondment.employee.full_name}',
                message=f'Получен запрос на возврат сотрудника {secondment.employee.full_name} в {secondment.from_division.name}',
                related_object_id=secondment.id,
                related_model='SecondmentRequest'
            )

        serializer = self.get_serializer(secondment)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve_return(self, request, pk=None):
        """Одобрить возврат сотрудника"""
        secondment = self.get_object()

        if not secondment.return_requested:
            return Response(
                {'error': 'Возврат не был запрошен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        secondment.approve_return(request.user)

        serializer = self.get_serializer(secondment)
        return Response(serializer.data)


class StaffingUnitViewSet(viewsets.ModelViewSet):
    """ViewSet для управления штатным расписанием"""

    queryset = StaffingUnit.objects.all()
    serializer_class = StaffingUnitSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['division__name', 'position__level']
    ordering = ['division__name', 'position__level']
    throttle_classes = [RoleRateThrottle]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтрация штатных единиц"""
        queryset = StaffingUnit.objects.select_related(
            'division', 'position', 'created_by'
        ).annotate(
            occupied=Count('division__employees', filter=Q(
                division__employees__position=F('position'),
                division__employees__is_active=True
            ))
        )

        # Фильтр по подразделению
        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(division_id=division_id)

        # Фильтр по должности
        position_id = self.request.query_params.get('position_id')
        if position_id:
            queryset = queryset.filter(position_id=position_id)

        # Фильтр по наличию вакансий
        has_vacancies = self.request.query_params.get('has_vacancies')
        if has_vacancies is not None:
            if has_vacancies.lower() == 'true':
                queryset = queryset.filter(quantity__gt=F('occupied'))
            else:
                queryset = queryset.filter(quantity__lte=F('occupied'))

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class VacancyViewSet(viewsets.ModelViewSet):
    """ViewSet для управления вакансиями"""

    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['priority', 'created_at']
    ordering = ['priority', '-created_at']
    throttle_classes = [RoleRateThrottle]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        elif self.action == 'close':
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        else:
            permission_classes = [IsAuthenticated, IsRole4 | IsRole5]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтрация вакансий"""
        queryset = Vacancy.objects.select_related(
            'staffing_unit', 'staffing_unit__division',
            'staffing_unit__position', 'created_by', 'closed_by'
        )

        # Фильтр по активности
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Фильтр по подразделению
        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(staffing_unit__division_id=division_id)

        # Фильтр по приоритету
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

        # Создаем уведомления
        instance = serializer.instance
        hr_admins = UserProfile.objects.filter(
            role=UserRole.ROLE_5,
            division_assignment=instance.staffing_unit.division
        )
        for profile in hr_admins:
            Notification.objects.create(
                recipient=profile.user,
                notification_type=NotificationType.VACANCY_CREATED,
                title=f'Создана новая вакансия: {instance.title}',
                message=f'В подразделении {instance.staffing_unit.division.name} создана вакансия на должность {instance.staffing_unit.position.name}',
                related_object_id=instance.id,
                related_model='Vacancy'
            )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Закрыть вакансию"""
        vacancy = self.get_object()

        if not vacancy.is_active:
            return Response(
                {'error': 'Вакансия уже закрыта'},
                status=status.HTTP_400_BAD_REQUEST
            )

        vacancy.close(request.user)

        serializer = self.get_serializer(vacancy)
        return Response(serializer.data)


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet для управления профилями пользователей"""

    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['user__username', 'role']
    ordering = ['user__username']
    throttle_classes = [RoleRateThrottle]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated, IsRole4]
        else:
            permission_classes = [IsAuthenticated, IsRole4]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтрация профилей"""
        queryset = UserProfile.objects.select_related(
            'user', 'division_assignment'
        )

        # Фильтр по роли
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        # Фильтр по подразделению
        division_id = self.request.query_params.get('division_id')
        if division_id:
            queryset = queryset.filter(division_assignment_id=division_id)
            return queryset
        else:
            permission_classes = [IsAuthenticated, IsRole4]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтрация подразделений на основе роли пользователя"""
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            return Division.objects.none()

        profile = user.profile
        queryset = Division.objects.select_related('parent_division', 'head_position')

        # Роли 1 и 4 видят все
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return queryset

        # Остальные роли видят только свои подразделения
        if not profile.division_assignment:
            return Division.objects.none()

        if profile.role == UserRole.ROLE_2 or (
            profile.role == UserRole.ROLE_5 and profile.include_child_divisions
        ):
            # Видят свое подразделение и всех потомков
            descendant_ids = _gather_descendant_ids(profile.division_assignment)
            queryset = queryset.filter(id__in=descendant_ids)
        else:
            # Видят только свое подразделение
            queryset = queryset.filter(id=profile.division_assignment.id)

        # Для роли 5 может быть ограничение по типу подразделения
        if profile.role == UserRole.ROLE_5 and profile.division_type_assignment:
            queryset = queryset.filter(division_type=profile.division_type_assignment)

        return queryset

    def perform_destroy(self, instance):
        """Проверка перед удалением подразделения"""
        # Проверяем наличие дочерних подразделений
        if instance.child_divisions.exists():
            raise ValidationError("Невозможно удалить подразделение с дочерними элементами")

        # Проверяем наличие сотрудников
        if instance.employees.filter(is_active=True).exists():
            raise ValidationError("Невозможно удалить подразделение с активными сотрудниками")

        super().perform_destroy(instance)

    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 5))  # Кэш на 5 минут
    def tree(self, request):
        """
        Получить иерархическое дерево всей организации.

        Query parameters:
        - include_employees: bool - включить сотрудников в дерево
        """
        include_employees = request.query_params.get('include_employees', 'false').lower() == 'true'

        # Получаем корневые подразделения (без родителя)
        root_divisions = self.get_queryset().filter(parent_division__isnull=True)

        tree_data = []
        for division in root_divisions:
            tree_data.append(_build_division_tree(division, include_employees))

        return Response(tree_data)

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """
        Переместить подразделение в другое место иерархии.

        Body parameters:
        - parent_id: int - ID нового родительского подразделения (null для корня)
        """
        division = self.get_object()
        parent_id = request.data.get('parent_id')

        if parent_id:
            try:
                new_parent = Division.objects.get(pk=parent_id)
            except Division.DoesNotExist:
                return Response(
                    {'error': 'Родительское подразделение не найдено'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Проверка на циклическую зависимость
            current = new_parent
            while current:
                if current.pk == division.pk:
                    return Response(
                        {'error': 'Невозможно переместить подразделение в свою же ветку'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                current = current.parent_division
        else:
            new_parent = None

        division.parent_division = new_parent
        try:
            division.save()
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(division)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'file': openapi.Schema(type=openapi.TYPE_FILE)
            },
            required=['file']
        )
    )
    def bulk_import(self, request):
        """
        Массовый импорт структуры организации из CSV файла.

        Формат CSV:
        name,code,division_type,parent_code,hierarchy_variant,description
        """
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'Файл не предоставлен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not uploaded_file.name.endswith('.csv'):
            return Response(
                {'error': 'Поддерживается только формат CSV'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            decoded_file = uploaded_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded_file))

            created_count = 0
            errors = []

            with transaction.atomic():
                # Первый проход - создаем подразделения без родителей
                divisions_by_code = {}
                rows = list(reader)

                for row_num, row in enumerate(rows, start=2):
                    try:
                        division = Division(
                            name=row['name'],
                            code=row.get('code', ''),
                            division_type=row['division_type'],
                            hierarchy_variant=row.get('hierarchy_variant', 'VARIANT_1'),
                            description=row.get('description', '')
                        )
                        division.save()
                        divisions_by_code[division.code] = division
                        created_count += 1
                    except Exception as e:
                        errors.append(f"Строка {row_num}: {str(e)}")

                # Второй проход - устанавливаем родительские связи
                for row_num, row in enumerate(rows, start=2):
                    parent_code = row.get('parent_code')
                    if parent_code and parent_code in divisions_by_code:
                        child_code = row.get('code', '')
                        if child_code in divisions_by_code:
                            child = divisions_by_code[child_code]
                            child.parent_division = divisions_by_code[parent_code]
                            try:
                                child.save()
                            except ValidationError as e:
                                errors.append(f"Строка {row_num}: {str(e)}")

            return Response({
                'created': created_count,
                'errors': errors
            })

        except Exception as e:
            return Response(
                {'error': f'Ошибка обработки файла: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Экспорт структуры организации в CSV.
        GET-параметр include_employees=true позволит добавить
        столбцы с сотрудниками.
        """
        include_employees = request.query_params.get('include_employees') == 'true'
        divisions = self.get_queryset()

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="organization_structure.csv"'
        writer = csv.writer(response)
        # Заголовки
        headers = ['ID', 'Название', 'Код', 'Тип', 'ID родителя', 'Код родителя', 'Вариант иерархии', 'Описание']
        if include_employees:
            headers += ['ID сотрудника', 'ФИО сотрудника', 'Должность', 'Табельный номер']
        writer.writerow(headers)

        for division in divisions:
            base = [
                division.id,
                division.name,
                division.code,
                division.get_division_type_display(),
                division.parent_division_id or '',
                division.parent_division.code if division.parent_division else '',
                division.get_hierarchy_variant_display(),
                division.description or ''
            ]
            if include_employees:
                emps = division.employees.filter(is_active=True).select_related('position')
                if emps:
                    for emp in emps:
                        writer.writerow(base + [
                            emp.id, emp.full_name, emp.position.name, emp.employee_number
                        ])
                else:
                    writer.writerow(base + ['', '', '', ''])
            else:
                writer.writerow(base)

        return response
