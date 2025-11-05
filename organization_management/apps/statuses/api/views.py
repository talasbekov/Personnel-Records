"""
API Views для управления статусами сотрудников
"""
from datetime import date
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from django.utils import timezone
from django.core.exceptions import ValidationError

from organization_management.apps.statuses.models import (
    EmployeeStatus,
    StatusDocument
)
from organization_management.apps.statuses.application.services import StatusApplicationService

from .serializers import (
    EmployeeStatusSerializer,
    EmployeeStatusDetailSerializer,
    EmployeeStatusCreateSerializer,
    EmployeeStatusExtendSerializer,
    EmployeeStatusTerminateSerializer,
    EmployeeStatusCancelSerializer,
    StatusDocumentSerializer,
    StatusDocumentUploadSerializer,
    DivisionHeadcountSerializer,
    AbsenceStatisticsSerializer,
    BulkStatusPlanSerializer
)

class EmployeeStatusViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления статусами сотрудников

    Endpoints:
    - GET /statuses/ - Список статусов
    - GET /statuses/{id}/ - Детальная информация о статусе
    - POST /statuses/ - Создание статуса
    - PUT/PATCH /statuses/{id}/ - Обновление статуса
    - DELETE /statuses/{id}/ - Удаление статуса
    - POST /statuses/{id}/extend/ - Продление статуса
    - POST /statuses/{id}/terminate/ - Досрочное завершение
    - POST /statuses/{id}/cancel/ - Отмена запланированного статуса
    - POST /statuses/{id}/upload_document/ - Загрузка документа
    - GET /statuses/current/ - Текущий статус сотрудника
    - GET /statuses/history/ - История статусов сотрудника
    - GET /statuses/planned/ - Запланированные статусы
    - POST /statuses/bulk_plan/ - Массовое планирование статусов
    - GET /statuses/division_headcount/ - Расход подразделения
    - GET /statuses/absence_statistics/ - Статистика по отсутствиям
    """
    queryset = EmployeeStatus.objects.all()
    serializer_class = EmployeeStatusSerializer
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = StatusApplicationService()

    def get_queryset(self):
        """Фильтрация queryset по правам пользователя"""
        user = self.request.user
        qs = super().get_queryset().select_related(
            'employee',
            'related_division',
            'created_by'
        ).prefetch_related(
            'documents',
            'change_history'
        )

        if not user.is_authenticated:
            return qs.none()

        # Пока возвращаем все статусы для аутентифицированных пользователей
        # TODO: Добавить проверку ролей после реализации системы ролей
        return qs

    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == 'retrieve':
            return EmployeeStatusDetailSerializer
        elif self.action == 'create':
            return EmployeeStatusCreateSerializer
        elif self.action == 'extend':
            return EmployeeStatusExtendSerializer
        elif self.action == 'terminate':
            return EmployeeStatusTerminateSerializer
        elif self.action == 'cancel':
            return EmployeeStatusCancelSerializer
        elif self.action == 'upload_document':
            return StatusDocumentUploadSerializer
        elif self.action == 'bulk_plan':
            return BulkStatusPlanSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        """Создание нового статуса"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            status_obj = self.service.create_status(
                employee_id=serializer.validated_data['employee'].id,
                status_type=serializer.validated_data['status_type'],
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data.get('end_date'),
                comment=serializer.validated_data.get('comment', ''),
                location=serializer.validated_data.get('location', ''),
                related_division_id=serializer.validated_data.get('related_division').id if serializer.validated_data.get('related_division') else None,
                user=request.user
            )
            output_serializer = EmployeeStatusSerializer(status_obj, context={'request': request})
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """
        Обновление статуса

        Бизнес-правила:
        - Запланированные статусы можно изменять до даты начала
        - Активные статусы можно изменять только через специальные методы (extend, terminate)
        """
        instance = self.get_object()

        # Проверка: можно ли изменять этот статус
        if instance.state == EmployeeStatus.StatusState.ACTIVE:
            return Response(
                {'error': 'Активный статус можно только продлить (extend) или завершить досрочно (terminate).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if instance.state == EmployeeStatus.StatusState.COMPLETED:
            return Response(
                {'error': 'Завершенный статус нельзя изменить.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if instance.state == EmployeeStatus.StatusState.CANCELLED:
            return Response(
                {'error': 'Отмененный статус нельзя изменить.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Разрешаем изменение только запланированных статусов
        if instance.state == EmployeeStatus.StatusState.PLANNED:
            today = timezone.now().date()
            if instance.start_date <= today:
                return Response(
                    {'error': 'Нельзя изменить статус, дата начала которого уже наступила.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
        Частичное обновление статуса

        Применяются те же правила, что и для полного обновления
        """
        instance = self.get_object()

        # Проверка: можно ли изменять этот статус
        if instance.state == EmployeeStatus.StatusState.ACTIVE:
            return Response(
                {'error': 'Активный статус можно только продлить (extend) или завершить досрочно (terminate).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if instance.state == EmployeeStatus.StatusState.COMPLETED:
            return Response(
                {'error': 'Завершенный статус нельзя изменить.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if instance.state == EmployeeStatus.StatusState.CANCELLED:
            return Response(
                {'error': 'Отмененный статус нельзя изменить.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Разрешаем изменение только запланированных статусов
        if instance.state == EmployeeStatus.StatusState.PLANNED:
            today = timezone.now().date()
            if instance.start_date <= today:
                return Response(
                    {'error': 'Нельзя изменить статус, дата начала которого уже наступила.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Удаление статуса

        Бизнес-правила:
        - Можно удалить только запланированные статусы до даты начала
        - Активные, завершенные и отмененные статусы удалить нельзя
        """
        instance = self.get_object()

        if instance.state != EmployeeStatus.StatusState.PLANNED:
            return Response(
                {'error': 'Можно удалить только запланированный статус. Используйте cancel для отмены.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        today = timezone.now().date()
        if instance.start_date <= today:
            return Response(
                {'error': 'Нельзя удалить статус, дата начала которого уже наступила.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        """
        Продление статуса

        Body: {
            "new_end_date": "2024-12-31"
        }
        """
        status_obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated_status = self.service.extend_status(
                status_id=status_obj.id,
                new_end_date=serializer.validated_data['new_end_date'],
                user=request.user
            )
            output_serializer = EmployeeStatusSerializer(updated_status, context={'request': request})
            return Response(output_serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """
        Досрочное завершение статуса

        Body: {
            "termination_date": "2024-11-15",
            "reason": "Причина досрочного завершения"
        }
        """
        status_obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated_status = self.service.terminate_status_early(
                status_id=status_obj.id,
                termination_date=serializer.validated_data['termination_date'],
                reason=serializer.validated_data['reason'],
                user=request.user
            )
            output_serializer = EmployeeStatusSerializer(updated_status, context={'request': request})
            return Response(output_serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Отмена запланированного статуса

        Body: {
            "reason": "Причина отмены"
        }
        """
        status_obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated_status = self.service.cancel_status(
                status_id=status_obj.id,
                reason=serializer.validated_data['reason'],
                user=request.user
            )
            output_serializer = EmployeeStatusSerializer(updated_status, context={'request': request})
            return Response(output_serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_document(self, request, pk=None):
        """
        Загрузка документа к статусу

        Body (multipart/form-data): {
            "title": "Название документа",
            "file": <file>,
            "description": "Описание" (optional)
        }
        """
        status_obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            document = self.service.attach_document(
                status_id=status_obj.id,
                title=serializer.validated_data['title'],
                file=serializer.validated_data['file'],
                description=serializer.validated_data.get('description', ''),
                user=request.user
            )
            output_serializer = StatusDocumentSerializer(document, context={'request': request})
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Получение текущего статуса сотрудника

        Query params:
        - employee_id (required): ID сотрудника
        - date (optional): Дата в формате YYYY-MM-DD (по умолчанию - сегодня)
        """
        employee_id = request.query_params.get('employee_id')
        date_str = request.query_params.get('date')

        if not employee_id:
            return Response(
                {'error': 'Параметр employee_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_date = date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты. Используйте YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_obj = self.service.get_employee_current_status(int(employee_id))

        if not status_obj:
            return Response({}, status=status.HTTP_200_OK)

        serializer = EmployeeStatusSerializer(status_obj, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Получение истории статусов сотрудника

        Query params:
        - employee_id (required): ID сотрудника
        - status_type (optional): Фильтр по типу статуса
        - start_date (optional): Начало периода (YYYY-MM-DD)
        - end_date (optional): Конец периода (YYYY-MM-DD)
        """
        employee_id = request.query_params.get('employee_id')
        if not employee_id:
            return Response(
                {'error': 'Параметр employee_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_type = request.query_params.get('status_type')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        try:
            start_date_val = date.fromisoformat(start_date_str) if start_date_str else None
            end_date_val = date.fromisoformat(end_date_str) if end_date_str else None
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты. Используйте YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.service.get_employee_status_history(
            employee_id=int(employee_id),
            status_type=status_type,
            start_date=start_date_val,
            end_date=end_date_val
        )

        serializer = EmployeeStatusSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def planned(self, request):
        """
        Получение запланированных статусов

        Query params:
        - employee_id (optional): ID сотрудника
        - division_id (optional): ID подразделения
        """
        employee_id = request.query_params.get('employee_id')
        division_id = request.query_params.get('division_id')

        queryset = self.service.get_planned_statuses(
            employee_id=int(employee_id) if employee_id else None,
            division_id=int(division_id) if division_id else None
        )

        serializer = EmployeeStatusSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_plan(self, request):
        """
        Массовое планирование статусов для нескольких сотрудников

        Body: {
            "employee_ids": [1, 2, 3],
            "status_type": "vacation",
            "start_date": "2024-12-01",
            "end_date": "2024-12-31",
            "comment": "Комментарий" (optional),
            "location": "Место" (optional),
            "related_division": 1 (optional)
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        created_statuses = []
        errors = []

        for employee_id in serializer.validated_data['employee_ids']:
            try:
                status_obj = self.service.plan_status(
                    employee_id=employee_id,
                    status_type=serializer.validated_data['status_type'],
                    start_date=serializer.validated_data['start_date'],
                    end_date=serializer.validated_data['end_date'],
                    comment=serializer.validated_data.get('comment', ''),
                    location=serializer.validated_data.get('location', ''),
                    related_division_id=serializer.validated_data.get('related_division'),
                    user=request.user
                )
                created_statuses.append(status_obj)
            except ValidationError as e:
                errors.append({
                    'employee_id': employee_id,
                    'error': str(e)
                })

        output_serializer = EmployeeStatusSerializer(
            created_statuses,
            many=True,
            context={'request': request}
        )

        response_data = {
            'created': output_serializer.data,
            'errors': errors
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def division_headcount(self, request):
        """
        Получение расхода подразделения на определенную дату

        Query params:
        - division_id (required): ID подразделения
        - date (optional): Дата в формате YYYY-MM-DD (по умолчанию - сегодня)
        """
        division_id = request.query_params.get('division_id')
        date_str = request.query_params.get('date')

        if not division_id:
            return Response(
                {'error': 'Параметр division_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_date = date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты. Используйте YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        headcount_data = self.service.get_division_headcount(
            division_id=int(division_id),
            target_date=target_date
        )

        serializer = DivisionHeadcountSerializer(headcount_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def absence_statistics(self, request):
        """
        Получение статистики по типам отсутствий за период

        Query params:
        - division_id (optional): ID подразделения
        - start_date (optional): Начало периода (YYYY-MM-DD)
        - end_date (optional): Конец периода (YYYY-MM-DD)
        """
        division_id = request.query_params.get('division_id')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        try:
            start_date_val = date.fromisoformat(start_date_str) if start_date_str else None
            end_date_val = date.fromisoformat(end_date_str) if end_date_str else None
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты. Используйте YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        statistics_data = self.service.get_absence_statistics(
            division_id=int(division_id) if division_id else None,
            start_date=start_date_val,
            end_date=end_date_val
        )

        serializer = AbsenceStatisticsSerializer(statistics_data)
        return Response(serializer.data)


class StatusDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра документов статусов

    Endpoints:
    - GET /status-documents/ - Список документов
    - GET /status-documents/{id}/ - Детальная информация о документе
    """
    queryset = StatusDocument.objects.all()
    serializer_class = StatusDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Фильтрация по статусу, если указан параметр"""
        queryset = super().get_queryset().select_related('status', 'uploaded_by')

        status_id = self.request.query_params.get('status_id')
        if status_id:
            queryset = queryset.filter(status_id=status_id)

        return queryset
