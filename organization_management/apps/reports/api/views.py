from rest_framework import viewsets, status
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

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Создание задачи на генерацию отчета.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save(created_by=request.user)
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
