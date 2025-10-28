from django.db import models
from django.conf import settings

class SecondmentRequest(models.Model):
    """Запрос на прикомандирование"""

    class ApprovalStatus(models.TextChoices):
        PENDING = 'pending', 'Ожидает одобрения'
        APPROVED = 'approved', 'Одобрен'
        REJECTED = 'rejected', 'Отклонен'
        CANCELLED = 'cancelled', 'Отменен'

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, null=True)
    from_division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.CASCADE,
        related_name='secondments_from',
        null=True
    )
    to_division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.CASCADE,
        related_name='secondments_to',
        null=True
    )
    start_date = models.DateField(default='1970-01-01')
    end_date = models.DateField(default='1970-01-01')
    reason = models.TextField(default='')
    status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_secondments'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_secondments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'secondment_requests'
