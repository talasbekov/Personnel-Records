from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import SecondmentRequestSerializer
from organization_management.apps.secondments.models import SecondmentRequest
from organization_management.apps.auth.permissions.rbac_permissions import CanEditOwnDirectorate
from organization_management.apps.statuses.models import EmployeeStatus

class SecondmentRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления запросами на прикомандирование.
    """
    queryset = SecondmentRequest.objects.all()
    serializer_class = SecondmentRequestSerializer

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'approve', 'reject', 'return']:
            self.permission_classes = [permissions.IsAuthenticated, CanEditOwnDirectorate]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Одобрение запроса на прикомандирование.
        """
        instance = self.get_object()
        instance.status = SecondmentRequest.ApprovalStatus.APPROVED
        instance.approved_by = request.user
        instance.save()

        # Создаем статусы
        EmployeeStatus.objects.create(
            employee=instance.employee,
            status_type=EmployeeStatus.StatusType.SECONDED_TO,
            start_date=instance.start_date,
            end_date=instance.end_date,
            related_division=instance.to_division,
            created_by=request.user
        )
        EmployeeStatus.objects.create(
            employee=instance.employee,
            status_type=EmployeeStatus.StatusType.SECONDED_FROM,
            start_date=instance.start_date,
            end_date=instance.end_date,
            related_division=instance.from_division,
            created_by=request.user
        )

        # ... (логика уведомления)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Отклонение запроса на прикомандирование.
        """
        instance = self.get_object()
        instance.status = SecondmentRequest.ApprovalStatus.REJECTED
        instance.rejection_reason = request.data.get('reason', '')
        instance.save()
        # ... (логика уведомления)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def return_employee(self, request, pk=None):
        """
        Возврат сотрудника из прикомандирования.
        """
        instance = self.get_object()
        # ... (логика возврата)
        return Response({'status': 'сотрудник возвращен'})

    @action(detail=False, methods=['get'])
    def incoming(self, request):
        """
        Список входящих запросов для текущего пользователя.
        """
        user = request.user
        queryset = self.get_queryset().filter(to_division__in=user.division.get_descendants(include_self=True))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def outgoing(self, request):
        """
        Список исходящих запросов от текущего пользователя.
        """
        user = request.user
        queryset = self.get_queryset().filter(requested_by=user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
