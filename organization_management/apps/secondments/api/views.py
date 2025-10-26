from __future__ import annotations
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from organization_management.apps.secondments.models import SecondmentRequest, SecondmentStatus
from .serializers import SecondmentRequestSerializer
from organization_management.apps.auth.models import UserRole
from organization_management.apps.notifications.models import Notification

class SecondmentRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing secondment requests."""

    queryset = SecondmentRequest.objects.all()
    serializer_class = SecondmentRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == UserRole.ROLE_4:
            return SecondmentRequest.objects.all()
        return SecondmentRequest.objects.filter(
            Q(from_division=user.division_assignment) |
            Q(to_division=user.division_assignment)
        )

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        instance = self.get_object()
        instance.status = SecondmentStatus.APPROVED
        instance.approved_by = request.user
        instance.save()
        Notification.objects.create(
            recipient=instance.requested_by,
            title='Запрос на прикомандирование одобрен',
            message=f'Ваш запрос на прикомандирование сотрудника {instance.employee.full_name} был одобрен.'
        )
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        instance = self.get_object()
        instance.status = SecondmentStatus.REJECTED
        instance.save()
        Notification.objects.create(
            recipient=instance.requested_by,
            title='Запрос на прикомандирование отклонен',
            message=f'Ваш запрос на прикомандирование сотрудника {instance.employee.full_name} был отклонен.'
        )
        return Response(self.get_serializer(instance).data)
