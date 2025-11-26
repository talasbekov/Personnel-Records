"""
Сервисный слой для управления статусами сотрудников
"""
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.db.models import Q, QuerySet
from django.core.exceptions import ValidationError
from django.utils import timezone

from organization_management.apps.statuses.models import (
    EmployeeStatus,
    StatusChangeHistory,
    StatusDocument
)
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division


class StatusApplicationService:
    """Сервис для управления статусами сотрудников"""

    @transaction.atomic
    def create_status(
        self,
        employee_id: int,
        status_type: str,
        start_date: date,
        end_date: Optional[date] = None,
        comment: str = "",
        location: str = "",
        related_division_id: Optional[int] = None,
        user=None
    ) -> EmployeeStatus:
        """
        Создание нового статуса сотрудника

        Args:
            employee_id: ID сотрудника
            status_type: Тип статуса
            start_date: Дата начала статуса
            end_date: Дата окончания статуса
            comment: Комментарий
            location: Место (для командировки/учебы)
            related_division_id: ID связанного подразделения (для прикомандирования)
            user: Пользователь, создавший статус

        Returns:
            EmployeeStatus: Созданный статус
        """
        try:
            employee = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            raise ValidationError(f"Сотрудник с ID {employee_id} не найден.")

        related_division = None
        if related_division_id:
            try:
                related_division = Division.objects.get(pk=related_division_id)
            except Division.DoesNotExist:
                raise ValidationError(f"Подразделение с ID {related_division_id} не найдено.")

        # =============================================================================
        # ПРОВЕРКА ДОСТУПНОСТИ СТАТУСОВ ДЛЯ ОТКОМАНДИРОВАННЫХ/ПРИКОМАНДИРОВАННЫХ
        # =============================================================================
        # Логика:
        # - Если сотрудник откомандирован (SECONDED_TO) - запрещаем локальные статусы
        # - Если сотрудник прикомандирован (SECONDED_FROM) - разрешаем локальные статусы
        # =============================================================================
        if status_type not in [EmployeeStatus.StatusType.SECONDED_FROM, EmployeeStatus.StatusType.SECONDED_TO]:
            # Проверяем активные статусы прикомандирования
            active_secondment = EmployeeStatus.objects.filter(
                employee_id=employee_id,
                status_type__in=[EmployeeStatus.StatusType.SECONDED_TO, EmployeeStatus.StatusType.SECONDED_FROM],
                state__in=[EmployeeStatus.StatusState.ACTIVE, EmployeeStatus.StatusState.PLANNED]
            ).filter(
                # Проверяем, что статус пересекается с запрашиваемым периодом
                Q(start_date__lte=start_date) &
                (Q(end_date__isnull=True) | Q(end_date__gte=start_date))
            ).first()

            if active_secondment:
                if active_secondment.status_type == EmployeeStatus.StatusType.SECONDED_TO:
                    # Сотрудник откомандирован - запрещаем локальные статусы
                    raise ValidationError(
                        f'Сотрудник откомандирован в подразделение "{active_secondment.related_division}" '
                        f'на период с {active_secondment.start_date} по {active_secondment.end_date or "не указано"}. '
                        f'В исходном подразделении нельзя устанавливать другие статусы, '
                        f'пока сотрудник откомандирован.'
                    )
                # Если SECONDED_FROM - разрешаем локальные статусы (сотрудник прикомандирован к нам)

        # Автоматически завершаем текущий активный статус, если новый статус не прикомандирование
        # и текущий статус тоже не прикомандирование
        # ВАЖНО: Завершаем только если новый статус уже начался (не запланированный в будущем)
        today = timezone.now().date()

        if (status_type not in [EmployeeStatus.StatusType.SECONDED_FROM, EmployeeStatus.StatusType.SECONDED_TO]
            and start_date <= today):  # Только для статусов, которые уже начались
            current_statuses = EmployeeStatus.objects.filter(
                employee_id=employee_id,
                state=EmployeeStatus.StatusState.ACTIVE,
                start_date__lt=start_date
            ).exclude(
                status_type__in=[EmployeeStatus.StatusType.SECONDED_FROM, EmployeeStatus.StatusType.SECONDED_TO]
            )

            for current_status in current_statuses:
                # Завершаем текущий статус датой, предшествующей новому статусу
                current_status.actual_end_date = start_date - timedelta(days=1)
                current_status.state = EmployeeStatus.StatusState.COMPLETED
                current_status.early_termination_reason = f"Автоматически завершен при установке нового статуса '{status_type}'"
                current_status.save()

                # Создаем запись в истории
                StatusChangeHistory.objects.create(
                    status=current_status,
                    change_type=StatusChangeHistory.ChangeType.TERMINATED,
                    changed_by=user,
                    comment=f"Автоматически завершен при создании нового статуса"
                )

        status = EmployeeStatus(
            employee=employee,
            status_type=status_type,
            start_date=start_date,
            end_date=end_date,
            comment=comment,
            location=location,
            related_division=related_division,
            created_by=user,
            actual_end_date=None,  # Явно устанавливаем None при создании
            early_termination_reason='',  # Пустая строка по умолчанию
            state=None  # Явно None, чтобы метод save() определил состояние по датам
        )
        status.save()

        # Создаем запись в истории изменений
        StatusChangeHistory.objects.create(
            status=status,
            change_type=StatusChangeHistory.ChangeType.CREATED,
            changed_by=user,
            comment=f"Создан статус '{status.get_status_type_display()}'"
        )

        return status

    @transaction.atomic
    def plan_status(
        self,
        employee_id: int,
        status_type: str,
        start_date: date,
        end_date: date,
        comment: str = "",
        location: str = "",
        related_division_id: Optional[int] = None,
        user=None
    ) -> EmployeeStatus:
        """
        Планирование будущего статуса сотрудника

        Args:
            employee_id: ID сотрудника
            status_type: Тип статуса
            start_date: Дата начала статуса (должна быть в будущем)
            end_date: Дата окончания статуса
            comment: Комментарий
            location: Место (для командировки/учебы)
            related_division_id: ID связанного подразделения
            user: Пользователь, создавший статус

        Returns:
            EmployeeStatus: Созданный запланированный статус
        """
        if start_date <= timezone.now().date():
            raise ValidationError("Дата начала запланированного статуса должна быть в будущем.")

        status = self.create_status(
            employee_id=employee_id,
            status_type=status_type,
            start_date=start_date,
            end_date=end_date,
            comment=comment,
            location=location,
            related_division_id=related_division_id,
            user=user
        )

        return status

    @transaction.atomic
    def extend_status(
        self,
        status_id: int,
        new_end_date: date,
        user=None
    ) -> EmployeeStatus:
        """
        Продление существующего статуса

        Args:
            status_id: ID статуса
            new_end_date: Новая дата окончания
            user: Пользователь, выполняющий продление

        Returns:
            EmployeeStatus: Обновленный статус
        """
        try:
            status = EmployeeStatus.objects.get(pk=status_id)
        except EmployeeStatus.DoesNotExist:
            raise ValidationError(f"Статус с ID {status_id} не найден.")

        status.extend(new_end_date, user)
        return status

    @transaction.atomic
    def terminate_status_early(
        self,
        status_id: int,
        termination_date: date,
        reason: str,
        user=None
    ) -> EmployeeStatus:
        """
        Досрочное завершение статуса

        Args:
            status_id: ID статуса
            termination_date: Дата досрочного завершения
            reason: Причина досрочного завершения
            user: Пользователь, выполняющий завершение

        Returns:
            EmployeeStatus: Обновленный статус
        """
        try:
            status = EmployeeStatus.objects.get(pk=status_id)
        except EmployeeStatus.DoesNotExist:
            raise ValidationError(f"Статус с ID {status_id} не найден.")

        if not reason:
            raise ValidationError("Необходимо указать причину досрочного завершения.")

        status.terminate_early(termination_date, reason, user)

        # Автоматически создаем статус "В строю" после завершения
        if status.status_type != EmployeeStatus.StatusType.IN_SERVICE:
            self.create_status(
                employee_id=status.employee_id,
                status_type=EmployeeStatus.StatusType.IN_SERVICE,
                start_date=termination_date + timedelta(days=1),
                user=user
            )

        return status

    @transaction.atomic
    def cancel_status(
        self,
        status_id: int,
        reason: str,
        user=None
    ) -> EmployeeStatus:
        """
        Отмена запланированного статуса

        Args:
            status_id: ID статуса
            reason: Причина отмены
            user: Пользователь, выполняющий отмену

        Returns:
            EmployeeStatus: Обновленный статус
        """
        try:
            status = EmployeeStatus.objects.get(pk=status_id)
        except EmployeeStatus.DoesNotExist:
            raise ValidationError(f"Статус с ID {status_id} не найден.")

        if not reason:
            raise ValidationError("Необходимо указать причину отмены.")

        status.cancel(reason, user)
        return status

    def get_employee_current_status(self, employee_id: int) -> Optional[EmployeeStatus]:
        """
        Получение текущего активного статуса сотрудника
        ПРИОРИТЕТ: статусы прикомандирования (SECONDED_TO, SECONDED_FROM) имеют наивысший приоритет

        Args:
            employee_id: ID сотрудника

        Returns:
            Optional[EmployeeStatus]: Текущий статус или None
        """
        today = timezone.now().date()

        # ПРИОРИТЕТ 1: Проверяем статусы прикомандирования (наивысший приоритет)
        secondment_status = EmployeeStatus.objects.filter(
            employee_id=employee_id,
            status_type__in=[EmployeeStatus.StatusType.SECONDED_TO, EmployeeStatus.StatusType.SECONDED_FROM],
            state__in=[EmployeeStatus.StatusState.ACTIVE, EmployeeStatus.StatusState.PLANNED],
            start_date__lte=today
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).order_by('-start_date').first()

        if secondment_status:
            return secondment_status

        # ПРИОРИТЕТ 2: Обычные статусы (если нет прикомандирования)
        return EmployeeStatus.objects.filter(
            employee_id=employee_id,
            state=EmployeeStatus.StatusState.ACTIVE,
            start_date__lte=today
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).exclude(
            status_type__in=[EmployeeStatus.StatusType.SECONDED_TO, EmployeeStatus.StatusType.SECONDED_FROM]
        ).order_by('-start_date').first()

    def get_employee_status_history(
        self,
        employee_id: int,
        status_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> QuerySet:
        """
        Получение истории статусов сотрудника

        Args:
            employee_id: ID сотрудника
            status_type: Фильтр по типу статуса
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            QuerySet: Список статусов
        """
        queryset = EmployeeStatus.objects.filter(
            employee_id=employee_id,
            state__in=[
                EmployeeStatus.StatusState.COMPLETED, EmployeeStatus.StatusState.CANCELLED
            ]
        ).order_by('-end_date')

        if status_type:
            queryset = queryset.filter(status_type=status_type)

        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(
                Q(end_date__lte=end_date) | Q(end_date__isnull=True)
            )

        return queryset.select_related('employee', 'related_division', 'created_by')

    def get_planned_statuses(
        self,
        employee_id: Optional[int] = None,
        division_id: Optional[int] = None
    ) -> QuerySet:
        """
        Получение запланированных статусов

        Args:
            employee_id: ID сотрудника (опционально)
            division_id: ID подразделения (опционально)

        Returns:
            QuerySet: Список запланированных статусов
        """
        queryset = EmployeeStatus.objects.filter(
            state=EmployeeStatus.StatusState.PLANNED
        )

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        if division_id:
            # Получаем сотрудников подразделения через StaffUnit
            from organization_management.apps.staff_unit.models import StaffUnit
            employee_ids = StaffUnit.objects.filter(
                division_id=division_id,
                employee__isnull=False
            ).values_list('employee_id', flat=True)
            queryset = queryset.filter(employee_id__in=employee_ids)

        return queryset.select_related('employee', 'related_division').order_by('start_date')

    @transaction.atomic
    def apply_planned_statuses(self, target_date: Optional[date] = None) -> List[EmployeeStatus]:
        """
        Применение запланированных статусов, дата начала которых наступила

        Args:
            target_date: Дата для применения (по умолчанию - сегодня)

        Returns:
            List[EmployeeStatus]: Список примененных статусов
        """
        if target_date is None:
            target_date = timezone.now().date()

        planned_statuses = EmployeeStatus.objects.filter(
            state=EmployeeStatus.StatusState.PLANNED,
            start_date__lte=target_date
        )

        applied_statuses = []
        for status in planned_statuses:
            status.state = EmployeeStatus.StatusState.ACTIVE
            status.auto_applied = True
            status.save()
            applied_statuses.append(status)

            # Создаем запись в истории
            StatusChangeHistory.objects.create(
                status=status,
                change_type=StatusChangeHistory.ChangeType.MODIFIED,
                old_value='planned',
                new_value='active',
                comment='Статус применен автоматически'
            )

        return applied_statuses

    @transaction.atomic
    def complete_expired_statuses(self, target_date: Optional[date] = None) -> List[EmployeeStatus]:
        """
        Завершение статусов, срок которых истек

        Args:
            target_date: Дата для проверки (по умолчанию - сегодня)

        Returns:
            List[EmployeeStatus]: Список завершенных статусов
        """
        if target_date is None:
            target_date = timezone.now().date()

        expired_statuses = EmployeeStatus.objects.filter(
            state=EmployeeStatus.StatusState.ACTIVE,
            end_date__lt=target_date
        )

        # Получаем системного пользователя для автоматических операций
        from django.contrib.auth.models import User
        system_user = User.objects.filter(is_superuser=True).first()

        completed_statuses = []
        for status in expired_statuses:
            old_pk = status.pk
            status.state = EmployeeStatus.StatusState.COMPLETED
            status.save()
            completed_statuses.append(status)

            # Автоматически создаем статус "В строю" после завершения
            # ТОЛЬКО если у сотрудника не осталось других активных статусов
            if status.status_type != EmployeeStatus.StatusType.IN_SERVICE:
                # Проверяем есть ли другие активные статусы ПОСЛЕ завершения текущего
                has_other_active = EmployeeStatus.objects.filter(
                    employee_id=status.employee_id,
                    state__in=[EmployeeStatus.StatusState.ACTIVE, EmployeeStatus.StatusState.PLANNED]
                ).exists()

                # Создаем IN_SERVICE только если нет других активных статусов
                if not has_other_active:
                    # Используем текущую дату если end_date в прошлом
                    new_start_date = max(
                        status.end_date + timedelta(days=1),
                        target_date
                    )
                    try:
                        self.create_status(
                            employee_id=status.employee_id,
                            status_type=EmployeeStatus.StatusType.IN_SERVICE,
                            start_date=new_start_date,
                            user=system_user
                        )
                    except ValidationError as e:
                        # Если не получилось создать IN_SERVICE - логируем но продолжаем
                        logger.warning(
                            f"Не удалось создать IN_SERVICE для сотрудника {status.employee_id} "
                            f"после завершения статуса {old_pk}: {e}"
                        )

        return completed_statuses

    @transaction.atomic
    def attach_document(
        self,
        status_id: int,
        title: str,
        file,
        description: str = "",
        user=None
    ) -> StatusDocument:
        """
        Прикрепление документа к статусу

        Args:
            status_id: ID статуса
            title: Название документа
            file: Файл документа
            description: Описание документа
            user: Пользователь, загрузивший документ

        Returns:
            StatusDocument: Созданный документ
        """
        try:
            status = EmployeeStatus.objects.get(pk=status_id)
        except EmployeeStatus.DoesNotExist:
            raise ValidationError(f"Статус с ID {status_id} не найден.")

        document = StatusDocument.objects.create(
            status=status,
            title=title,
            file=file,
            description=description,
            uploaded_by=user
        )

        return document

    def get_division_headcount(
        self,
        division_id: int,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Получение расхода подразделения на определенную дату

        Args:
            division_id: ID подразделения
            target_date: Дата для расчета (по умолчанию - сегодня)

        Returns:
            Dict: Статистика по расходу
        """
        if target_date is None:
            target_date = timezone.now().date()

        # Получаем всех сотрудников подразделения
        from organization_management.apps.staff_unit.models import StaffUnit
        staff_units = StaffUnit.objects.filter(
            division_id=division_id,
            employee__isnull=False
        ).select_related('employee')

        total_count = staff_units.count()
        in_service_count = 0
        absent_by_type = {}

        for staff_unit in staff_units:
            # Получаем статус сотрудника на указанную дату
            status = EmployeeStatus.objects.filter(
                employee=staff_unit.employee,
                start_date__lte=target_date
            ).filter(
                Q(end_date__gte=target_date) | Q(end_date__isnull=True)
            ).filter(
                state__in=[EmployeeStatus.StatusState.ACTIVE, EmployeeStatus.StatusState.PLANNED]
            ).first()

            if status:
                if status.status_type == EmployeeStatus.StatusType.IN_SERVICE:
                    in_service_count += 1
                else:
                    status_display = status.get_status_type_display()
                    absent_by_type[status_display] = absent_by_type.get(status_display, 0) + 1
            else:
                in_service_count += 1

        return {
            'division_id': division_id,
            'date': target_date,
            'total_count': total_count,
            'in_service_count': in_service_count,
            'absent_count': total_count - in_service_count,
            'absent_by_type': absent_by_type
        }

    def get_absence_statistics(
        self,
        division_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Получение статистики по типам отсутствий за период и количеству штата

        Args:
            division_id: ID подразделения (опционально, если None - вся организация)
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Dict: Статистика по отсутствиям и количеству штата
        """
        if start_date is None:
            start_date = timezone.now().date() - timedelta(days=30)
        if end_date is None:
            end_date = timezone.now().date()

        # Получаем количество штата (сотрудников)
        from organization_management.apps.staff_unit.models import StaffUnit
        from organization_management.apps.divisions.models import Division

        if division_id:
            # Для конкретного подразделения и всех дочерних
            try:
                division = Division.objects.get(pk=division_id)
                # Получаем все дочерние подразделения включая само подразделение
                division_ids = list(
                    division.get_descendants(include_self=True).values_list('id', flat=True)
                )
            except Division.DoesNotExist:
                division_ids = [division_id]

            staff_count = StaffUnit.objects.filter(
                division_id__in=division_ids,
                employee__isnull=False
            ).count()

            employee_ids = StaffUnit.objects.filter(
                division_id__in=division_ids,
                employee__isnull=False
            ).values_list('employee_id', flat=True)
        else:
            # Для всей организации
            staff_count = StaffUnit.objects.filter(
                employee__isnull=False
            ).count()

            employee_ids = None

        # Статистика по статусам
        queryset = EmployeeStatus.objects.filter(
            start_date__lte=end_date
        ).filter(
            Q(end_date__gte=start_date) | Q(end_date__isnull=True)
        ).exclude(
            status_type=EmployeeStatus.StatusType.IN_SERVICE
        )

        if employee_ids is not None:
            queryset = queryset.filter(employee_id__in=employee_ids)

        # Подсчет по типам (используем код статуса на английском)
        statistics = {}
        for status_type, display_name in EmployeeStatus.StatusType.choices:
            if status_type == EmployeeStatus.StatusType.IN_SERVICE:
                continue
            count = queryset.filter(status_type=status_type).count()
            statistics[status_type] = count

        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'division_id': division_id,
            'staff_count': staff_count,
            'total_absences': queryset.count(),
            'by_type': statistics
        }
