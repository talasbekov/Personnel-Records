from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from organization_management.apps.reports.models import Report
from .serializers import ReportSerializer
from organization_management.apps.reports.tasks import generate_report_task

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer

    @action(detail=False, methods=['post'])
    def generate_report(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            report = serializer.save()
            generate_report_task.delay(report.id)
            return Response({'status': 'report generation started'}, status=status.HTTP_202_ACCEPTED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
