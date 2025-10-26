from __future__ import annotations
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

class Report(models.Model):
    """Модель отчета"""

    class ReportType(models.TextChoices):
        PERSONNEL_ROSTER = 'personnel_roster', 'Расход личного состава'
        DIVISION_REPORT = 'division_report', 'Отчет по подразделению'
        STAFFING_TABLE = 'staffing_table', 'Штатное расписание'
        STATUS_SUMMARY = 'status_summary', 'Сводка по статусам'

    class ReportFormat(models.TextChoices):
        DOCX = 'docx', 'Word документ'
        XLSX = 'xlsx', 'Excel таблица'
        PDF = 'pdf', 'PDF документ'

    class JobStatus(models.TextChoices):
        PENDING = 'pending', 'В очереди'
        PROCESSING = 'processing', 'Генерируется'
        COMPLETED = 'completed', 'Готов'
        FAILED = 'failed', 'Ошибка'

    report_type = models.CharField(max_length=50, choices=ReportType.choices)
    report_format = models.CharField(max_length=10, choices=ReportFormat.choices)

    # Параметры отчета
    division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    filters = models.JSONField(default=dict, blank=True)

    # Результат
    job_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING
    )
    file = models.FileField(upload_to='reports/', null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Метаданные
    created_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reports'

    def __str__(self):
        return f"Report {self.id} - {self.get_report_type_display()}"
