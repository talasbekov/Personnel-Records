from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile

from organization_management.apps.reports.models import Report
from organization_management.apps.reports.infrastructure.generators.docx_generator import (
    DOCXGenerator,
)
from organization_management.apps.reports.infrastructure.generators.xlsx_generator import (
    XLSXGenerator,
)
from organization_management.apps.reports.infrastructure.generators.pdf_generator import (
    PDFGenerator,
)
from organization_management.apps.reports.infrastructure.data_aggregator import DataAggregator
from organization_management.apps.notifications.services.websocket_service import (
    send_report_ready_notification,
)

@shared_task
def generate_report_task(report_id):
    """Асинхронная генерация отчета"""
    report = Report.objects.get(id=report_id)
    report.status = Report.JobStatus.PROCESSING
    report.save()

    try:
        # Сбор данных
        aggregator = DataAggregator()
        data = aggregator.collect_data(report)

        # Генерация файла
        if report.report_format == Report.ReportFormat.DOCX:
            generator = DOCXGenerator()
        elif report.report_format == Report.ReportFormat.XLSX:
            generator = XLSXGenerator()
        else:
            generator = PDFGenerator()

        filename, content_bytes = generator.generate(data, report)

        # Сохранение
        report.file.save(filename, ContentFile(content_bytes))
        report.status = Report.JobStatus.COMPLETED
        report.completed_at = timezone.now()
        report.save()

        # Отправка уведомления
        send_report_ready_notification(report)

    except Exception as e:
        report.status = Report.JobStatus.FAILED
        report.error_message = str(e)
        report.save()
