from datetime import timedelta
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class EmployeeStatus(models.Model):
    """Модель статуса сотрудника"""

    class StatusType(models.TextChoices):
        IN_SERVICE      =   'in_service',       'В строю'
        VACATION        =   'vacation',         'Отпуск'
        LEAVE_BY_REPORT =   'leave_by_report',  'Отпуск по рапорту'
        SICK_LEAVE      =   'sick_leave',       'Больничный'
        BUSINESS_TRIP   =   'business_trip',    'Командировка'
        TRAINING        =   'training',         'Учёба'
        COMPETITION     =   'competition',      'На соревнованиях'
        OTHER_ABSENCE   =   'other_absence',    'Отсутствие по иным причинам'
        ON_DUTY         =   'on_duty',          'На дежурстве'
        AFTER_DUTY      =   'after_duty',       'После дежурства'
        SECONDED_FROM   =   'seconded_from',    'Прикомандирован из'
        SECONDED_TO     =   'seconded_to',      'Откомандирован в'

    class StatusState(models.TextChoices):
        PLANNED = 'planned', 'Запланирован'
        ACTIVE = 'active', 'Активен'
        COMPLETED = 'completed', 'Завершен'
        CANCELLED = 'cancelled', 'Отменен'

    # Основная информация
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='statuses',
        verbose_name='Сотрудник'
    )
    status_type = models.CharField(
        max_length=20,
        choices=StatusType.choices,
        default=StatusType.IN_SERVICE,
        verbose_name='Тип статуса'
    )
    state = models.CharField(
        max_length=20,
        choices=StatusState.choices,
        default=StatusState.ACTIVE,
        verbose_name='Состояние статуса'
    )

    # Даты
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата окончания'
    )
    actual_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Фактическая дата окончания',
        help_text='Используется при досрочном завершении статуса'
    )

    # Дополнительная информация
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    early_termination_reason = models.TextField(
        blank=True,
        verbose_name='Причина досрочного завершения'
    )

    # Специфические поля для разных типов статусов
    related_division = models.ForeignKey(
        'divisions.Division',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Связанное подразделение',
        help_text='Для прикомандирования - подразделение источник/назначение'
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Место',
        help_text='Место командировки/учебы'
    )

    # Служебная информация
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_statuses',
        verbose_name='Создал'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    # Флаги
    is_notified = models.BooleanField(
        default=False,
        verbose_name='Уведомление отправлено',
        help_text='Уведомление о предстоящем статусе отправлено'
    )
    auto_applied = models.BooleanField(
        default=False,
        verbose_name='Применен автоматически',
        help_text='Статус был применен автоматически по расписанию'
    )

    class Meta:
        db_table = 'employee_statuses'
        verbose_name = 'Статус сотрудника'
        verbose_name_plural = 'Статусы сотрудников'
        ordering = ['-start_date', '-created_at']
        indexes = [
            models.Index(fields=['employee', 'state']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['state', 'start_date']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.get_status_type_display()} ({self.start_date})"

    def clean(self):
        """Валидация модели"""
        # Проверка корректности интервала дат
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': "Дата окончания не может быть раньше даты начала."
            })

        # Проверка фактической даты окончания
        if self.actual_end_date:
            # Для досрочного завершения actual_end_date может быть раньше end_date - это нормально
            # Проверяем только что actual_end_date не раньше start_date
            if self.actual_end_date < self.start_date:
                raise ValidationError({
                    'actual_end_date': "Фактическая дата окончания не может быть раньше даты начала."
                })
            # Убрали проверку actual_end_date > end_date, так как при автозавершении
            # старых статусов actual_end_date специально ставится раньше end_date

        # Проверка, что дата начала не в прошлом (только для новых статусов)
        today = timezone.now().date()
        if not self.pk and self.start_date and self.start_date < today:
            raise ValidationError({
                'start_date': f"Нельзя создавать статус на прошедшую дату. Дата начала должна быть не раньше {today}."
            })

        # Проверка, что дата начала не раньше даты приема сотрудника
        if self.employee_id:
            from organization_management.apps.employees.models import Employee
            try:
                employee = Employee.objects.get(pk=self.employee_id)
                if self.start_date < employee.hire_date:
                    raise ValidationError({
                        'start_date': f"Дата начала статуса не может быть раньше даты приема сотрудника ({employee.hire_date})."
                    })
            except Employee.DoesNotExist:
                pass

        # Статус "В строю" не должен иметь даты окончания
        if self.status_type == self.StatusType.IN_SERVICE and self.end_date:
            raise ValidationError({
                'end_date': 'Статус "В строю" не должен иметь дату окончания.'
            })

        # Остальные статусы должны иметь дату окончания
        if self.status_type != self.StatusType.IN_SERVICE and not self.end_date and self.state != self.StatusState.PLANNED:
            raise ValidationError({
                'end_date': 'Для данного типа статуса требуется указать дату окончания.'
            })

        # Проверка максимальной длительности отпуска (по умолчанию 45 дней, настраивается)
        if self.status_type == self.StatusType.VACATION and self.start_date and self.end_date:
            max_vacation_days = getattr(settings, 'MAX_VACATION_DAYS', 45)
            vacation_duration = (self.end_date - self.start_date).days + 1

            if vacation_duration > max_vacation_days:
                raise ValidationError({
                    'end_date': f'Длительность непрерывного отпуска не может превышать {max_vacation_days} дней. '
                               f'Текущая длительность: {vacation_duration} дней.'
                })

        # Проверка пересечений с другими активными статусами
        # Запрещаем создавать пересекающиеся статусы для одного сотрудника
        if self.employee_id and self.start_date:
            # Определяем конечную дату для проверки
            check_end_date = self.end_date or timezone.now().date() + timedelta(days=36500)  # 100 лет в будущее

            # Ищем пересекающиеся активные статусы, исключая текущий редактируемый статус
            overlapping = EmployeeStatus.objects.filter(
                employee_id=self.employee_id,
                state__in=[self.StatusState.ACTIVE, self.StatusState.PLANNED]
            )
            
            # ВАЖНО: Исключаем текущий редактируемый статус из проверки
            # Это позволяет редактировать существующие статусы без блокировки
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)

            for other_status in overlapping:
                today = timezone.now().date()

                # ИСКЛЮЧЕНИЕ 1: Разрешаем пересечение с "В строю" для запланированных статусов
                # так как "В строю" будет автоматически завершен при активации нового статуса
                # Также разрешаем создание "В строю" при наличии запланированных статусов
                is_planned_status = self.start_date > today
                is_other_planned = other_status.start_date > today
                is_self_in_service = self.status_type == self.StatusType.IN_SERVICE
                is_other_in_service = other_status.status_type == self.StatusType.IN_SERVICE

                # Случай 1: Создаем запланированный статус, а есть активный "В строю"
                if is_planned_status and is_other_in_service:
                    continue

                # Случай 2: Создаем "В строю", а есть запланированные статусы в будущем
                # "В строю" будет автоматически завершен когда запланированный статус активируется
                if is_self_in_service and is_other_planned:
                    continue

                # ИСКЛЮЧЕНИЕ 2: Разрешаем создание или редактирование статуса на сегодняшний день
                # Это позволяет исправлять ошибки или менять статус на сегодня
                # (например, сотрудник заболел в обед, нужно изменить его статус)
                # При этом предыдущий статус будет автоматически завершен
                is_status_today = self.start_date == today
                is_other_status_today = other_status.start_date == today

                if is_status_today and is_other_status_today:
                    # Разрешаем создавать/редактировать статус на сегодня, который заменит существующий
                    # Предыдущий статус нужно будет завершить при сохранении
                    continue

                # ИСКЛЮЧЕНИЕ 3: Разрешаем пересечение статусов прикомандирования друг с другом
                # При прикомандировании создаются ДВА статуса одновременно (SECONDED_TO и SECONDED_FROM)
                # для одного сотрудника, поэтому они должны мочь сосуществовать
                is_self_secondment = self.status_type in [self.StatusType.SECONDED_TO, self.StatusType.SECONDED_FROM]
                is_other_secondment = other_status.status_type in [self.StatusType.SECONDED_TO, self.StatusType.SECONDED_FROM]

                if is_self_secondment and is_other_secondment:
                    # Разрешаем пересечение статусов прикомандирования
                    continue

                # ИСКЛЮЧЕНИЕ 4: Статусы прикомандирования имеют наивысший приоритет
                # Они могут пересекаться с любыми другими статусами, так как показываются в первую очередь
                # Это позволяет откомандированному сотруднику сохранять свой основной статус (например, "В строю")
                # но при этом отображаться с приоритетным статусом "Откомандирован"
                if is_self_secondment or is_other_secondment:
                    # Разрешаем пересечение статусов прикомандирования с любыми другими статусами
                    continue

                other_end = other_status.end_date or timezone.now().date() + timedelta(days=36500)

                # Проверяем пересечение периодов
                if not (check_end_date < other_status.start_date or self.start_date > other_end):
                    raise ValidationError({
                        'start_date': f'Период статуса пересекается с существующим статусом '
                                     f'"{other_status.get_status_type_display()}" '
                                     f'({other_status.start_date} - {other_status.end_date or "не указано"}). '
                                     f'Для одного сотрудника не может быть пересекающихся активных статусов.'
                    })

    def save(self, *args, **kwargs):
        """Переопределенный метод сохранения"""
        # Автоматически устанавливаем состояние в зависимости от дат
        today = timezone.now().date()

        # Для новых записей (pk отсутствует) автоматически определяем состояние если оно не указано
        is_new = self.pk is None

        if is_new and not self.state:
            # Только для новых записей без явно указанного state
            if self.start_date > today:
                self.state = self.StatusState.PLANNED
            elif self.actual_end_date and self.actual_end_date < today:
                self.state = self.StatusState.COMPLETED
            elif self.end_date and self.end_date < today:
                self.state = self.StatusState.COMPLETED
            else:
                self.state = self.StatusState.ACTIVE
        elif not is_new and self.state in [self.StatusState.ACTIVE, self.StatusState.PLANNED]:
            # Для существующих записей с ACTIVE/PLANNED пересчитываем автоматически
            if self.start_date > today:
                self.state = self.StatusState.PLANNED
            elif self.actual_end_date and self.actual_end_date < today:
                self.state = self.StatusState.COMPLETED
            elif self.end_date and self.end_date < today:
                self.state = self.StatusState.COMPLETED
            else:
                self.state = self.StatusState.ACTIVE

        self.full_clean()
        super().save(*args, **kwargs)

    def extend(self, new_end_date, user=None):
        """Продление статуса"""
        if self.state != self.StatusState.ACTIVE:
            raise ValidationError("Можно продлить только активный статус.")

        if new_end_date <= self.end_date:
            raise ValidationError("Новая дата окончания должна быть позже текущей.")

        old_end_date = self.end_date
        self.end_date = new_end_date
        self._skip_history_log = True  # Пропускаем автоматическое логирование
        self.save()

        # Создаем запись в истории изменений вручную с более подробной информацией
        StatusChangeHistory.objects.create(
            status=self,
            change_type=StatusChangeHistory.ChangeType.EXTENDED,
            old_value=str(old_end_date),
            new_value=str(new_end_date),
            changed_by=user,
            comment=f"Продление статуса с {old_end_date} до {new_end_date}"
        )

    def terminate_early(self, termination_date, reason, user=None):
        """Досрочное завершение статуса"""
        if self.state != self.StatusState.ACTIVE:
            raise ValidationError("Можно досрочно завершить только активный статус.")

        if termination_date < self.start_date:
            raise ValidationError("Дата завершения не может быть раньше даты начала.")

        if self.end_date and termination_date >= self.end_date:
            raise ValidationError("Дата досрочного завершения должна быть раньше плановой даты.")

        self.actual_end_date = termination_date
        self.early_termination_reason = reason
        self.state = self.StatusState.COMPLETED
        self._skip_history_log = True  # Пропускаем автоматическое логирование
        self.save()

        # Создаем запись в истории изменений вручную с более подробной информацией
        StatusChangeHistory.objects.create(
            status=self,
            change_type=StatusChangeHistory.ChangeType.TERMINATED,
            old_value=str(self.end_date),
            new_value=str(termination_date),
            changed_by=user,
            comment=f"Досрочное завершение: {reason}"
        )

    def cancel(self, reason, user=None):
        """Отмена запланированного статуса"""
        if self.state != self.StatusState.PLANNED:
            raise ValidationError("Можно отменить только запланированный статус.")

        self.state = self.StatusState.CANCELLED
        self.early_termination_reason = reason
        self._skip_history_log = True  # Пропускаем автоматическое логирование
        self.save()

        # Создаем запись в истории изменений вручную с более подробной информацией
        StatusChangeHistory.objects.create(
            status=self,
            change_type=StatusChangeHistory.ChangeType.CANCELLED,
            changed_by=user,
            comment=f"Отмена запланированного статуса: {reason}"
        )

    @property
    def effective_end_date(self):
        """Возвращает фактическую дату окончания или плановую"""
        return self.actual_end_date or self.end_date

    @property
    def is_active(self):
        """Проверка, является ли статус активным на текущую дату"""
        if not self.start_date:
            return False

        today = timezone.now().date()
        return (
            self.state == self.StatusState.ACTIVE and
            self.start_date <= today and
            (not self.effective_end_date or self.effective_end_date >= today)
        )

    @property
    def is_planned(self):
        """Проверка, является ли статус запланированным"""
        return self.state == self.StatusState.PLANNED


class StatusChangeHistory(models.Model):
    """История изменений статусов"""

    class ChangeType(models.TextChoices):
        CREATED = 'created', 'Создан'
        EXTENDED = 'extended', 'Продлен'
        TERMINATED = 'terminated', 'Досрочно завершен'
        CANCELLED = 'cancelled', 'Отменен'
        MODIFIED = 'modified', 'Изменен'

    status = models.ForeignKey(
        EmployeeStatus,
        on_delete=models.CASCADE,
        related_name='change_history',
        verbose_name='Статус'
    )
    change_type = models.CharField(
        max_length=20,
        choices=ChangeType.choices,
        verbose_name='Тип изменения'
    )
    old_value = models.TextField(
        blank=True,
        verbose_name='Старое значение'
    )
    new_value = models.TextField(
        blank=True,
        verbose_name='Новое значение'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Изменил'
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата изменения'
    )

    class Meta:
        db_table = 'employee_status_change_history'
        verbose_name = 'История изменения статуса'
        verbose_name_plural = 'История изменений статусов'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.status} - {self.get_change_type_display()} ({self.changed_at})"


class StatusDocument(models.Model):
    """Документы, прикрепленные к статусу"""

    status = models.ForeignKey(
        EmployeeStatus,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Статус'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Название документа'
    )
    file = models.FileField(
        upload_to='status_documents/%Y/%m/',
        verbose_name='Файл'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Загрузил'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )

    class Meta:
        db_table = 'employee_status_documents'
        verbose_name = 'Документ статуса'
        verbose_name_plural = 'Документы статусов'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} - {self.status}"
