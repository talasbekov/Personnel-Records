from celery import shared_task
from organization_management.apps.reports.models import Report
from organization_management.apps.notifications.models import Notification

@shared_task
def generate_report_task(report_id):
    report = Report.objects.get(id=report_id)
    # TODO: Implement report generation logic
    report.status = 'SUCCESS'
    report.save()
    Notification.objects.create(
        recipient=report.created_by,
        title='Отчет готов',
        message=f'Ваш отчет {report.name} готов к скачиванию.'
    )
