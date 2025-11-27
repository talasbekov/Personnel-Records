from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import SecondmentRequestSerializer
from organization_management.apps.secondments.models import SecondmentRequest

from organization_management.apps.divisions.models import Division
from django.db.models import Q
from django.utils import timezone
from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.notifications.models import Notification

class SecondmentRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления запросами на прикомандирование.
    """
    queryset = SecondmentRequest.objects.all().order_by('-created_at')
    serializer_class = SecondmentRequestSerializer

    def _get_department_root(self, division: Division) -> Division:
        node = division
        while node.parent and node.division_type != Division.DivisionType.DEPARTMENT:
            node = node.parent
        return node

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if not user.is_authenticated:
            return qs.none()

        # Проверяем наличие роли
        if not hasattr(user, 'role_info'):
            return qs.none()

        role_code = user.role_info.get_role_code()

        # ROLE_4 (Системный администратор) видит все
        if role_code == 'ROLE_4':
            return qs

        # Проверяем наличие подразделения для ролей с областью видимости
        user_division = user.role_info.effective_scope_division
        if not user_division:
            return qs.none()

        # Для остальных — запросы, где источник/приемник в зоне видимости подразделения пользователя
        # Используем get_descendants для получения всех дочерних подразделений
        allowed = user_division.get_descendants(include_self=True)
        allowed_ids = allowed.values_list("id", flat=True)

        return qs.filter(Q(from_division_id__in=allowed_ids) | Q(to_division_id__in=allowed_ids))

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'approve', 'reject', 'return']:
            self.permission_classes = [permissions.IsAuthenticated]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    def perform_create(self, serializer):
        """
        Создание заявки на прикомандирование.
        Автоматически определяет from_division по подразделению сотрудника.
        """
        user = self.request.user
        employee = serializer.validated_data.get('employee')
        from_division = serializer.validated_data.get('from_division')

        # Если from_division не указано вручную, определяем автоматически
        if not from_division:
            if employee and hasattr(employee, 'staff_unit') and employee.staff_unit:
                from_division = employee.staff_unit.division
            else:
                # Если у сотрудника нет staff_unit, используем подразделение пользователя
                if hasattr(user, 'role_info'):
                    from_division = user.role_info.effective_scope_division
                else:
                    from_division = None

            # Проверяем, что from_division определено
            if not from_division:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'employee': 'Не удалось определить исходное подразделение сотрудника. '
                               'Убедитесь что сотрудник имеет штатную единицу.'
                })

        # Проверяем, что создатель связан с from_division
        # Пользователь должен иметь доступ к from_division (оно в его зоне ответственности)
        if hasattr(user, 'role_info'):
            user_division = user.role_info.effective_scope_division
            if user_division:
                allowed = user_division.get_descendants(include_self=True)
                if from_division.id not in allowed.values_list('id', flat=True):
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied(
                        'Вы не можете создавать заявки на прикомандирование для сотрудников '
                        'из подразделений вне вашей зоны ответственности.'
                    )

        # Сохраняем заявку с from_division (автоматически определенным или указанным вручную)
        serializer.save(
            requested_by=user,
            from_division=from_division
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Одобрение запроса на прикомандирование.
        """
        instance = self.get_object()
        instance.status = SecondmentRequest.ApprovalStatus.APPROVED
        instance.approved_by = request.user

        # Проверка прав: только ROLE_3 (Начальник управления) может одобрять прикомандирование
        if hasattr(request.user, 'role_info'):
            role_code = request.user.role_info.get_role_code()

            # Только ROLE_3 и ROLE_4 могут одобрять
            if role_code not in ['ROLE_3', 'ROLE_4']:
                return Response({
                    'detail': 'Только начальник управления (ROLE_3) может одобрять прикомандирование.'
                }, status=403)

            # Для ROLE_3 проверяем что to_division в его зоне ответственности
            if role_code == 'ROLE_3':
                user_division = request.user.role_info.effective_scope_division
                if user_division:
                    allowed = user_division.get_descendants(include_self=True)
                    if instance.to_division_id not in allowed.values_list('id', flat=True):
                        return Response({
                            'detail': 'Одобрение вне вашего управления запрещено.'
                        }, status=403)
        # Валидация перед одобрением
        # 1. Удаляем ВСЕ старые статусы прикомандирования для этого сотрудника
        # Это необходимо, чтобы избежать пересечения периодов при создании новых статусов
        # При новом прикомандировании старые статусы становятся неактуальными
        # Удаляем независимо от state, чтобы избежать проблем с некорректными данными
        EmployeeStatus.objects.filter(
            employee_id=instance.employee_id,
            status_type__in=[EmployeeStatus.StatusType.SECONDED_TO, EmployeeStatus.StatusType.SECONDED_FROM],
        ).delete()

        # 2. Проверяем что сотрудник активен (имеет статус "В строю")
        active_in_service = EmployeeStatus.objects.filter(
            employee_id=instance.employee_id,
            status_type=EmployeeStatus.StatusType.IN_SERVICE,
            state=EmployeeStatus.StatusState.ACTIVE,
        ).exists()

        if not active_in_service:
            return Response({
                'detail': 'Сотрудник должен иметь активный статус "В строю" для прикомандирования.'
            }, status=400)

        instance.save()

        # ====================================================================
        # ВАЖНО: Создание двух статусов прикомандирования
        # ====================================================================
        # При прикомандировании создаются ДВА статуса для ОДНОГО сотрудника:
        #
        # 1. SECONDED_TO (Откомандирован в) - для исходного подразделения
        #    - Показывает что сотрудник откомандирован В другое подразделение
        #    - related_division = целевое подразделение (куда отправлен)
        #    - Учитывается при подсчете headcount исходного подразделения
        #
        # 2. SECONDED_FROM (Прикомандирован из) - для принимающего подразделения
        #    - Показывает что сотрудник прикомандирован ИЗ другого подразделения
        #    - related_division = исходное подразделение (откуда пришел)
        #    - Учитывается при подсчете headcount принимающего подразделения
        #
        # Это позволяет:
        # - Каждому подразделению видеть прикомандированных сотрудников
        # - Корректно учитывать сотрудников в отчетах по численности
        # - Отслеживать "движение" сотрудников между подразделениями
        #
        # При формировании отчетов необходимо учитывать оба статуса
        # чтобы избежать двойного подсчета одного сотрудника.
        # ====================================================================

        # Откомандирован в (для собственного подразделения)
        # state определяется автоматически в save() на основе start_date
        EmployeeStatus.objects.create(
            employee_id=instance.employee_id,
            status_type=EmployeeStatus.StatusType.SECONDED_TO,
            start_date=instance.start_date,
            end_date=instance.end_date,
            related_division_id=instance.to_division_id,
            created_by=request.user,
            comment=f"Откомандирован в подразделение {instance.to_division_id}",
        )
        # Прикомандирован (для принимающего подразделения)
        EmployeeStatus.objects.create(
            employee_id=instance.employee_id,
            status_type=EmployeeStatus.StatusType.SECONDED_FROM,
            start_date=instance.start_date,
            end_date=instance.end_date,
            related_division_id=instance.from_division_id,
            created_by=request.user,
            comment=f"Прикомандирован из подразделения {instance.from_division_id}",
        )

        # Отправляем уведомление создателю заявки
        from organization_management.apps.notifications.services.websocket_service import send_notification
        from organization_management.apps.notifications.models import Notification

        # Отправляем уведомление пользователю, который создал заявку
        if instance.requested_by:
            send_notification(
                recipient_id=instance.requested_by.id,
                notification_type=Notification.NotificationType.SECONDMENT_APPROVED,
                title=f"Заявка на прикомандирование одобрена: {str(instance.employee)}",
                message=(
                    f"Ваша заявка на прикомандирование сотрудника {str(instance.employee)} "
                    f"в подразделение «{instance.to_division.name}» была одобрена. "
                    f"Период: {instance.start_date} - {instance.end_date}."
                ),
                link=f"/api/secondments/secondment-requests/{instance.id}/",
                related_object_id=instance.id,
                related_model="SecondmentRequest",
                payload={
                    "secondment_request_id": instance.id,
                    "employee_id": instance.employee.id,
                    "approved_by": request.user.id,
                },
            )

        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Отклонение запроса на прикомандирование.
        """
        instance = self.get_object()
        instance.status = SecondmentRequest.ApprovalStatus.REJECTED
        instance.rejected_by = request.user
        instance.rejection_reason = request.data.get('reason', '')

        # Проверка прав: только ROLE_3 (Начальник управления) может отклонять прикомандирование
        if hasattr(request.user, 'role_info'):
            role_code = request.user.role_info.get_role_code()

            # Только ROLE_3 и ROLE_4 могут отклонять
            if role_code not in ['ROLE_3', 'ROLE_4']:
                return Response({
                    'detail': 'Только начальник управления (ROLE_3) может отклонять прикомандирование.'
                }, status=403)

            # Для ROLE_3 проверяем что to_division в его зоне ответственности
            if role_code == 'ROLE_3':
                user_division = request.user.role_info.effective_scope_division
                if user_division:
                    allowed = user_division.get_descendants(include_self=True)
                    if instance.to_division_id not in allowed.values_list('id', flat=True):
                        return Response({
                            'detail': 'Отклонение вне вашего управления запрещено.'
                        }, status=403)

        instance.save()

        # Отправка уведомлений через WebSocket
        from organization_management.apps.notifications.services.websocket_service import send_notification

        rejection_reason = instance.rejection_reason or 'Не указана'

        # Уведомление создателю заявки (руководителю исходного подразделения)
        if instance.from_division and hasattr(instance.from_division, 'head') and instance.from_division.head:
            creator = instance.from_division.head.user if hasattr(instance.from_division.head, 'user') else None
            if creator:
                send_notification(
                    recipient_id=creator.id,
                    notification_type=Notification.NotificationType.SECONDMENT_REJECTED,
                    title=f'Заявка на прикомандирование отклонена: {str(instance.employee)}',
                    message=(
                        f'Ваша заявка на прикомандирование сотрудника {str(instance.employee)} '
                        f'из подразделения «{instance.from_division.name}» в «{instance.to_division.name}» '
                        f'на период с {instance.start_date} по {instance.end_date} отклонена. '
                        f'Причина: {rejection_reason}'
                    ),
                    link=f'/api/secondments/secondment-requests/{instance.id}/',
                    related_object_id=instance.id,
                    related_model="SecondmentRequest",
                    payload={
                        "secondment_request_id": instance.id,
                        "employee_id": instance.employee.id,
                        "rejected_by": request.user.id,
                        "rejection_reason": rejection_reason,
                    },
                )

        # Уведомление сотруднику (если у него есть пользователь)
        if hasattr(instance.employee, 'user') and instance.employee.user:
            send_notification(
                recipient_id=instance.employee.user.id,
                notification_type=Notification.NotificationType.SECONDMENT_REJECTED,
                title='Заявка на ваше прикомандирование отклонена',
                message=(
                    f'Заявка на ваше прикомандирование '
                    f'из подразделения «{instance.from_division.name}» в «{instance.to_division.name}» '
                    f'на период с {instance.start_date} по {instance.end_date} отклонена. '
                    f'Причина: {rejection_reason}'
                ),
                link=f'/api/secondments/secondment-requests/{instance.id}/',
                related_object_id=instance.id,
                related_model="SecondmentRequest",
                payload={
                    "secondment_request_id": instance.id,
                    "employee_id": instance.employee.id,
                    "rejected_by": request.user.id,
                    "rejection_reason": rejection_reason,
                },
            )

        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def return_employee(self, request, pk=None):
        """
        Досрочный возврат сотрудника из прикомандирования.
        Завершает активные статусы прикомандирования, связанные с этой заявкой.
        """
        instance = self.get_object()
        today = timezone.now().date()

        # Проверяем что заявка одобрена
        if instance.status != SecondmentRequest.ApprovalStatus.APPROVED:
            return Response({
                'detail': 'Можно вернуть только из одобренного прикомандирования.'
            }, status=400)

        # Находим активные или будущие статусы прикомандирования для этого сотрудника и заявки
        # Используем Q для поиска статусов без end_date ИЛИ с end_date в будущем
        secondment_to_status = EmployeeStatus.objects.filter(
            employee_id=instance.employee_id,
            status_type=EmployeeStatus.StatusType.SECONDED_TO,
            state__in=[EmployeeStatus.StatusState.ACTIVE, EmployeeStatus.StatusState.PLANNED],
            related_division_id=instance.to_division_id,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).order_by('-start_date').first()

        secondment_from_status = EmployeeStatus.objects.filter(
            employee_id=instance.employee_id,
            status_type=EmployeeStatus.StatusType.SECONDED_FROM,
            state__in=[EmployeeStatus.StatusState.ACTIVE, EmployeeStatus.StatusState.PLANNED],
            related_division_id=instance.from_division_id,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).order_by('-start_date').first()

        if not secondment_to_status and not secondment_from_status:
            return Response({
                'detail': 'Не найдены активные статусы прикомандирования для этой заявки.'
            }, status=404)

        # Завершаем статусы через save() для вызова валидации
        if secondment_to_status:
            # Для запланированных статусов (которые еще не начались) - отменяем
            # Для активных статусов - завершаем досрочно
            if secondment_to_status.start_date > today:
                secondment_to_status.state = EmployeeStatus.StatusState.CANCELLED
            else:
                secondment_to_status.actual_end_date = today
                secondment_to_status.state = EmployeeStatus.StatusState.COMPLETED
            secondment_to_status.save()

        if secondment_from_status:
            # Для запланированных статусов (которые еще не начались) - отменяем
            # Для активных статусов - завершаем досрочно
            if secondment_from_status.start_date > today:
                secondment_from_status.state = EmployeeStatus.StatusState.CANCELLED
            else:
                secondment_from_status.actual_end_date = today
                secondment_from_status.state = EmployeeStatus.StatusState.COMPLETED
            secondment_from_status.save()

        # Обновляем статус заявки
        instance.status = SecondmentRequest.ApprovalStatus.CANCELLED
        instance.save()

        # Отправляем уведомления о возврате сотрудника
        from organization_management.apps.notifications.services.websocket_service import send_notification
        from organization_management.apps.notifications.models import Notification

        # Уведомление руководителю исходного подразделения (откомандировавшему)
        if instance.from_division and hasattr(instance.from_division, 'head') and instance.from_division.head:
            from_head = instance.from_division.head.user if hasattr(instance.from_division.head, 'user') else None
            if from_head:
                send_notification(
                    recipient_id=from_head.id,
                    notification_type=Notification.NotificationType.SECONDMENT_APPROVED,  # Используем APPROVED как положительное событие
                    title=f'Сотрудник возвращен из прикомандирования: {str(instance.employee)}',
                    message=(
                        f'Сотрудник {str(instance.employee)} досрочно возвращен '
                        f'из прикомандирования в подразделение «{instance.to_division.name}». '
                        f'Дата возврата: {today}.'
                    ),
                    link=f'/api/secondments/secondment-requests/{instance.id}/',
                    related_object_id=instance.id,
                    related_model="SecondmentRequest",
                    payload={
                        "secondment_request_id": instance.id,
                        "employee_id": instance.employee.id,
                        "returned_date": str(today),
                        "returned_by": request.user.id,
                    },
                )

        # Уведомление руководителю принимающего подразделения
        if instance.to_division and hasattr(instance.to_division, 'head') and instance.to_division.head:
            to_head = instance.to_division.head.user if hasattr(instance.to_division.head, 'user') else None
            if to_head:
                send_notification(
                    recipient_id=to_head.id,
                    notification_type=Notification.NotificationType.SECONDMENT_APPROVED,
                    title=f'Прикомандированный сотрудник возвращен: {str(instance.employee)}',
                    message=(
                        f'Прикомандированный сотрудник {str(instance.employee)} '
                        f'досрочно возвращен в исходное подразделение «{instance.from_division.name}». '
                        f'Дата возврата: {today}.'
                    ),
                    link=f'/api/secondments/secondment-requests/{instance.id}/',
                    related_object_id=instance.id,
                    related_model="SecondmentRequest",
                    payload={
                        "secondment_request_id": instance.id,
                        "employee_id": instance.employee.id,
                        "returned_date": str(today),
                        "returned_by": request.user.id,
                    },
                )

        return Response({
            'status': 'сотрудник досрочно возвращен',
            'returned_date': today,
            'closed_statuses': {
                'seconded_to': secondment_to_status.id if secondment_to_status else None,
                'seconded_from': secondment_from_status.id if secondment_from_status else None,
            }
        })

    @action(detail=False, methods=['get'])
    def incoming(self, request):
        """
        Список входящих запросов для текущего пользователя (принимающая сторона).
        Показывает ТОЛЬКО заявки со статусом PENDING, которые ожидают одобрения,
        где to_division находится в управлении пользователя (определяется через employee).
        """
        user = request.user

        # Получаем управление пользователя через его employee
        user_department = None
        if hasattr(user, 'employee') and user.employee:
            if hasattr(user.employee, 'staff_unit') and user.employee.staff_unit:
                # Поднимаемся до управления (DEPARTMENT)
                user_department = self._get_department_root(user.employee.staff_unit.division)

        # Если не удалось определить управление через employee, используем effective_scope_division
        if not user_department:
            if not hasattr(user, 'role_info'):
                return Response([])

            user_division = user.role_info.effective_scope_division
            if not user_division:
                return Response([])

            user_department = self._get_department_root(user_division)

        if not user_department:
            return Response([])

        # Получаем все дочерние подразделения управления
        allowed = user_department.get_descendants(include_self=True)

        # Фильтруем заявки где to_division в управлении пользователя И статус PENDING
        queryset = self.get_queryset().filter(
            to_division__in=allowed,
            status=SecondmentRequest.ApprovalStatus.PENDING
        )
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
