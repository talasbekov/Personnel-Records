from rest_framework import viewsets, status
from django.db import models
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import ReportSerializer
from organization_management.apps.reports.models import Report
from organization_management.apps.reports.tasks import generate_report_task

class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления отчетами.
    """
    queryset = Report.objects.all()
    serializer_class = ReportSerializer

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if not user.is_authenticated:
            return qs.none()
        role = getattr(user, "role", None)
        if role in (user.RoleType.SYSTEM_ADMIN, user.RoleType.OBSERVER_ORG):  # type: ignore[attr-defined]
            return qs

        # Разрешить видеть свои отчеты и отчеты по доступной зоне ответственности (если указано division)
        from organization_management.apps.divisions.models import Division
        if not user.division_id:
            return qs.filter(created_by_id=user.id)

        # Определяем доступные подразделения
        if role == user.RoleType.HR_ADMIN:  # type: ignore[attr-defined]
            allowed = user.division.get_descendants(include_self=True)
        else:
            # Роли 2/3/6 — по своему департаменту
            node = user.division
            while node.parent and node.division_type != Division.DivisionType.DEPARTMENT:
                node = node.parent
            allowed = node.get_descendants(include_self=True)

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
            role = getattr(user, 'role', None)
            if role not in (user.RoleType.SYSTEM_ADMIN, user.RoleType.OBSERVER_ORG):
                # Вычислим допустимую зону
                if not user.division_id:
                    return Response({'detail': 'Нет зоны ответственности'}, status=403)
                node = user.division
                if role == user.RoleType.HR_ADMIN:
                    allowed = node.get_descendants(include_self=True)
                else:
                    while node.parent and node.division_type != Division.DivisionType.DEPARTMENT:
                        node = node.parent
                    allowed = node.get_descendants(include_self=True)
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
