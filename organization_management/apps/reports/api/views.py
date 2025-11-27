from rest_framework import viewsets, status, permissions
from django.db import models
from django.http import FileResponse
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .serializers import ReportSerializer
from organization_management.apps.reports.models import Report
from organization_management.apps.reports.tasks import generate_report_task
from organization_management.apps.reports.utils import generate_personnel_expense_report
from organization_management.apps.divisions.models import Division
import os

class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления отчетами.
    """
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    http_method_names = ['get']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        if not user.is_authenticated:
            return qs.none()

        # Суперпользователь видит все
        if user.is_superuser:
            return qs

        # Получаем роль пользователя
        user_division = None
        role_code = None
        if hasattr(user, 'role_info'):
            user_division = user.role_info.get_user_division()
            role_code = user.role_info.get_role_code()

        # Если нет подразделения - видит только свои отчеты
        if not user_division:
            return qs.filter(created_by_id=user.id)

        # Определяем доступные подразделения
        allowed = user_division.get_descendants(include_self=True)

        return qs.filter(
            models.Q(created_by_id=user.id) |
            models.Q(division_id__in=allowed.values_list("id", flat=True))
        )

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Создание задачи на генерацию отчета.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Проверка зоны ответственности для выбранного division
        division_id = serializer.validated_data.get('division')
        user = request.user

        if division_id:
            from organization_management.apps.divisions.models import Division
            try:
                div = Division.objects.get(pk=division_id.id if hasattr(division_id, 'id') else division_id)
            except Division.DoesNotExist:
                return Response({'detail': 'Некорректное подразделение'}, status=400)

            # Суперпользователь может создавать отчеты для любого подразделения
            if not user.is_superuser:
                # Получаем подразделение пользователя
                user_division = None
                if hasattr(user, 'role_info'):
                    user_division = user.role_info.get_user_division()

                if not user_division:
                    return Response({'detail': 'Нет зоны ответственности'}, status=403)

                # Проверяем, что запрашиваемое подразделение в области видимости
                allowed = user_division.get_descendants(include_self=True)
                if div.id not in allowed.values_list('id', flat=True):
                    return Response({'detail': 'Подразделение вне зоны ответственности'}, status=403)

        report = serializer.save(created_by=user)
        generate_report_task.delay(report.id)
        return Response({'job_id': report.job_id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Проверка статуса задачи.
        """
        report = self.get_object()
        return Response({'status': report.status})

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Скачивание готового отчета.
        """
        report = self.get_object()
        if report.file:
            #  (логика для редиректа на файл)
            return Response({'download_url': report.file.url})
        else:
            return Response({'status': 'файл еще не готов'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Дата для определения статусов сотрудников (формат: YYYY-MM-DD). Если не указана, используется текущая дата.',
                required=False
            )
        ],
        responses={
            200: {
                'type': 'string',
                'format': 'binary',
                'description': 'Excel файл отчета "Расход"'
            }
        }
    )
    @action(
        detail=False,
        methods=['get'],
        url_path='expense',
        permission_classes=[permissions.IsAuthenticated]
    )
    def expense(self, request):
        """
        Генерация и скачивание отчета "Расход" по департаменту пользователя.
        GET /api/reports/reports/expense/?date=2025-11-22

        Система автоматически определяет департамент пользователя.
        Опционально можно указать дату для определения статусов сотрудников.
        """
        user = request.user

        # Получаем дату из query параметра или используем текущую
        report_date = request.query_params.get('date')
        if report_date:
            from datetime import datetime
            try:
                report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'detail': 'Неверный формат даты. Используйте YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            from datetime import date
            report_date = date.today()

        # Определяем департамент пользователя
        department = None

        if user.is_superuser:
            # Суперпользователь может выбрать любой департамент (берем первый)
            department = Division.objects.filter(
                division_type=Division.DivisionType.DEPARTMENT,
                is_active=True
            ).first()
        else:
            # Получаем подразделение пользователя
            user_division = None
            if hasattr(user, 'role_info'):
                user_division = user.role_info.get_user_division()

            if not user_division:
                return Response(
                    {'detail': 'Не удалось определить подразделение пользователя'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Поднимаемся до департамента (level=1)
            current = user_division
            while current and current.level > 1:
                current = current.parent

            if current and current.level == 1 and current.division_type == Division.DivisionType.DEPARTMENT:
                department = current
            else:
                return Response(
                    {'detail': 'Не удалось определить департамент пользователя'},
                    status=status.HTTP_403_FORBIDDEN
                )

        if not department:
            return Response(
                {'detail': 'Департамент не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Генерируем отчет
        try:
            file_buffer, filename = generate_personnel_expense_report(department.id, report_date)

            response = FileResponse(
                file_buffer,
                as_attachment=True,
                filename=filename,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            return response

        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'detail': f'Ошибка при генерации отчета: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Дата для определения статусов сотрудников (формат: YYYY-MM-DD). Если не указана, используется текущая дата.',
                required=False
            )
        ],
        responses={
            200: {
                'type': 'string',
                'format': 'binary',
                'description': 'Excel файл отчета "Организация"'
            }
        }
    )
    @action(
        detail=False,
        methods=['get'],
        url_path='organization',
        permission_classes=[permissions.IsAuthenticated]
    )
    def organization(self, request):
        """
        Генерация и скачивание отчета "Организация" по всем департаментам.
        GET /api/reports/reports/organization/?date=2025-11-27

        Отчет включает данные по всем активным департаментам организации.
        Опционально можно указать дату для определения статусов сотрудников.
        """
        # Получаем дату из query параметра или используем текущую
        report_date = request.query_params.get('date')
        if report_date:
            from datetime import datetime
            try:
                report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'detail': 'Неверный формат даты. Используйте YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            from datetime import date
            report_date = date.today()

        # Генерируем отчет
        try:
            from organization_management.apps.reports.utils import generate_organization_report
            file_buffer, filename = generate_organization_report(report_date)

            response = FileResponse(
                file_buffer,
                as_attachment=True,
                filename=filename,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            return response

        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'detail': f'Ошибка при генерации отчета: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
