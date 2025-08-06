"""
Сериализаторы для приложения управления персоналом.

Полный набор сериализаторов для всех моделей и операций согласно ТЗ.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from .models import (
    Division, Position, Employee, UserProfile, SecondmentRequest,
    EmployeeStatusLog, StaffingUnit, Vacancy, DivisionStatusUpdate,
    PersonnelReport, EmployeeTransferLog, UserRole, EmployeeStatusType,
    DivisionType, SecondmentStatus, VacancyPriority
)


class PositionSerializer(serializers.ModelSerializer):
    """Сериализатор для должностей"""

    class Meta:
        model = Position
        fields = [
            'id', 'name', 'level', 'description', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_level(self, value):
        """Валидация уровня должности"""
        if value < 1 or value > 100:
            raise serializers.ValidationError(
                "Уровень должности должен быть от 1 до 100"
            )
        return value


class DivisionSerializer(serializers.ModelSerializer):
    """Базовый сериализатор для подразделений"""

    parent_division_name = serializers.CharField(
        source='parent_division.name',
        read_only=True
    )
    division_type_display = serializers.CharField(
        source='get_division_type_display',
        read_only=True
    )
    hierarchy_variant_display = serializers.CharField(
        source='get_hierarchy_variant_display',
        read_only=True
    )
    head_position_name = serializers.CharField(
        source='head_position.name',
        read_only=True
    )
    employee_count = serializers.SerializerMethodField()
    child_divisions_count = serializers.SerializerMethodField()

    class Meta:
        model = Division
        fields = [
            'id', 'name', 'code', 'division_type', 'division_type_display',
            'parent_division', 'parent_division_name',
            'hierarchy_variant', 'hierarchy_variant_display',
            'description', 'contact_info', 'head_position', 'head_position_name',
            'employee_count', 'child_divisions_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_employee_count(self, obj):
        return obj.employees.filter(is_active=True).count()

    def get_child_divisions_count(self, obj):
        return obj.child_divisions.count()

    def validate(self, attrs):
        """Комплексная валидация подразделения"""
        parent = attrs.get('parent_division')
        division_type = attrs.get('division_type', self.instance.division_type if self.instance else None)
        hierarchy_variant = attrs.get('hierarchy_variant', self.instance.hierarchy_variant if self.instance else None)

        if parent and division_type and hierarchy_variant:
            # Валидация иерархии
            if hierarchy_variant == 'VARIANT_1':
                allowed_parents = {
                    DivisionType.DEPARTMENT: [DivisionType.COMPANY],
                    DivisionType.MANAGEMENT: [DivisionType.DEPARTMENT],
                    DivisionType.OFFICE: [DivisionType.MANAGEMENT],
                }
            elif hierarchy_variant == 'VARIANT_2':
                allowed_parents = {
                    DivisionType.MANAGEMENT: [DivisionType.COMPANY],
                    DivisionType.OFFICE: [DivisionType.MANAGEMENT],
                }
            else:  # VARIANT_3
                allowed_parents = {
                    DivisionType.OFFICE: [DivisionType.COMPANY],
                }

            if division_type in allowed_parents:
                if parent.division_type not in allowed_parents[division_type]:
                    raise serializers.ValidationError({
                        'parent_division': f'{division_type} не может подчиняться {parent.division_type} в варианте {hierarchy_variant}'
                    })

        return attrs


class DivisionDetailSerializer(DivisionSerializer):
    """Детальный сериализатор подразделения с дополнительной информацией"""

    staffing_units = serializers.SerializerMethodField()
    active_vacancies = serializers.SerializerMethodField()
    status_indicator = serializers.SerializerMethodField()

    class Meta(DivisionSerializer.Meta):
        fields = DivisionSerializer.Meta.fields + [
            'staffing_units', 'active_vacancies', 'status_indicator'
        ]

    def get_staffing_units(self, obj):
        """Штатное расписание подразделения"""
        units = obj.staffing_units.select_related('position')
        return StaffingUnitShortSerializer(units, many=True).data

    def get_active_vacancies(self, obj):
        """Активные вакансии в подразделении"""
        vacancies = Vacancy.objects.filter(
            staffing_unit__division=obj,
            is_active=True
        ).count()
        return vacancies

    def get_status_indicator(self, obj):
        """Индикатор обновления статусов"""
        today = timezone.now().date()
        status_update = DivisionStatusUpdate.objects.filter(
            division=obj,
            update_date=today
        ).first()

        if status_update and status_update.is_updated:
            return 'GREEN'
        else:
            return 'RED'


class DivisionTreeSerializer(serializers.ModelSerializer):
    """Сериализатор для древовидного представления"""

    children = serializers.SerializerMethodField()

    class Meta:
        model = Division
        fields = ['id', 'name', 'code', 'division_type', 'children']

    def get_children(self, obj):
        children = obj.child_divisions.all()
        return DivisionTreeSerializer(children, many=True).data


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя"""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class EmployeeSerializer(serializers.ModelSerializer):
    """Базовый сериализатор сотрудника"""

    position_name = serializers.CharField(source='position.name', read_only=True)
    position_level = serializers.IntegerField(source='position.level', read_only=True)
    division_name = serializers.CharField(source='division.name', read_only=True)
    division_full_path = serializers.CharField(source='division.get_full_path', read_only=True)
    current_status = serializers.SerializerMethodField()
    current_status_display = serializers.SerializerMethodField()
    acting_for_position_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_number', 'full_name', 'photo',
            'position', 'position_name', 'position_level',
            'division', 'division_name', 'division_full_path',
            'acting_for_position', 'acting_for_position_name',
            'hired_date', 'is_active', 'fired_date',
            'contact_phone', 'contact_email', 'notes',
            'current_status', 'current_status_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['employee_number', 'created_at', 'updated_at']

    def get_acting_for_position_name(self, obj):
        return obj.acting_for_position.name if obj.acting_for_position else None

    def get_current_status(self, obj):
        return obj.get_current_status()

    def get_current_status_display(self, obj):
        status = obj.get_current_status()
        return EmployeeStatusType(status).label

    def validate_contact_phone(self, value):
        """Валидация телефона"""
        if value:
            # Убираем все символы кроме цифр и +
            cleaned = ''.join(c for c in value if c.isdigit() or c == '+')
            if len(cleaned) < 10:
                raise serializers.ValidationError("Некорректный номер телефона")
            return cleaned
        return value


class EmployeeDetailSerializer(EmployeeSerializer):
    """Детальный сериализатор сотрудника"""

    user = UserSerializer(read_only=True)
    recent_statuses = serializers.SerializerMethodField()
    transfer_history = serializers.SerializerMethodField()
    is_seconded = serializers.SerializerMethodField()
    secondment_info = serializers.SerializerMethodField()

    class Meta(EmployeeSerializer.Meta):
        fields = EmployeeSerializer.Meta.fields + [
            'user', 'recent_statuses', 'transfer_history',
            'is_seconded', 'secondment_info'
        ]

    def get_recent_statuses(self, obj):
        """Последние 5 статусов"""
        statuses = obj.status_logs.all()[:5]
        return EmployeeStatusLogShortSerializer(statuses, many=True).data

    def get_transfer_history(self, obj):
        """История переводов"""
        transfers = obj.transfer_logs.all()[:5]
        return EmployeeTransferLogShortSerializer(transfers, many=True).data

    def get_is_seconded(self, obj):
        """Прикомандирован ли сотрудник"""
        return obj.is_seconded_out() or obj.is_seconded_in()

    def get_secondment_info(self, obj):
        """Информация о прикомандировании"""
        if obj.is_seconded_out():
            log = obj.status_logs.filter(
                status=EmployeeStatusType.SECONDED_OUT,
                date_to__isnull=True
            ).first()
            if log and log.secondment_division:
                return {
                    'type': 'seconded_out',
                    'division_id': log.secondment_division.id,
                    'division_name': log.secondment_division.name,
                    'date_from': log.date_from
                }
        elif obj.is_seconded_in():
            # Ищем активный запрос на прикомандирование
            request = SecondmentRequest.objects.filter(
                employee=obj,
                status=SecondmentStatus.APPROVED,
                date_from__lte=timezone.now().date()
            ).filter(
                Q(date_to__gte=timezone.now().date()) | Q(date_to__isnull=True)
            ).first()
            if request:
                return {
                    'type': 'seconded_in',
                    'division_id': request.from_division.id,
                    'division_name': request.from_division.name,
                    'date_from': request.date_from
                }
        return None


class EmployeeStatusSerializer(serializers.Serializer):
    """Сериализатор для статуса сотрудника"""

    status = serializers.CharField()
    status_display = serializers.CharField()
    date_from = serializers.DateField()
    date_to = serializers.DateField(allow_null=True)
    comment = serializers.CharField(allow_blank=True)
    secondment_division_id = serializers.IntegerField(allow_null=True)
    secondment_division_name = serializers.CharField(allow_null=True)


class EmployeeStatusLogSerializer(serializers.ModelSerializer):
    """Сериализатор журнала статусов"""

    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    secondment_division_name = serializers.CharField(
        source='secondment_division.name',
        read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = EmployeeStatusLog
        fields = [
            'id', 'employee', 'employee_name',
            'status', 'status_display',
            'date_from', 'date_to', 'comment',
            'secondment_division', 'secondment_division_name',
            'is_auto_copied', 'created_at', 'created_by', 'created_by_name',
            'updated_at', 'updated_by'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]

    def validate(self, attrs):
        """Валидация статуса"""
        employee = attrs.get('employee', self.instance.employee if self.instance else None)
        date_from = attrs.get('date_from', self.instance.date_from if self.instance else None)
        date_to = attrs.get('date_to', self.instance.date_to if self.instance else None)
        status = attrs.get('status', self.instance.status if self.instance else None)

        if date_to and date_from > date_to:
            raise serializers.ValidationError({
                'date_to': 'Дата окончания не может быть раньше даты начала'
            })

        # Проверка пересечений
        if employee and date_from:
            overlapping = EmployeeStatusLog.objects.filter(
                employee=employee,
                date_from__lte=date_to if date_to else timezone.now().date() + timezone.timedelta(days=365)
            ).filter(
                Q(date_to__gte=date_from) | Q(date_to__isnull=True)
            )

            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            # Некоторые статусы могут сосуществовать
            coexisting_statuses = [
                EmployeeStatusType.SECONDED_OUT,
                EmployeeStatusType.SECONDED_IN
            ]

            if status not in coexisting_statuses:
                overlapping = overlapping.exclude(status__in=coexisting_statuses)

            if overlapping.exists():
                raise serializers.ValidationError(
                    'Статус конфликтует с существующим статусом за этот период'
                )

        return attrs


class EmployeeStatusLogShortSerializer(serializers.ModelSerializer):
    """Краткий сериализатор журнала статусов"""

    status_display = serializers.CharField(source='get_status_display')

    class Meta:
        model = EmployeeStatusLog
        fields = ['id', 'status', 'status_display', 'date_from', 'date_to']


class BulkStatusUpdateSerializer(serializers.Serializer):
    """Сериализатор для массового обновления статусов"""

    employee_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=EmployeeStatusType.choices)
    date_from = serializers.DateField()
    date_to = serializers.DateField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate_employee_id(self, value):
        """Проверка существования сотрудника"""
        if not Employee.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Активный сотрудник с ID {value} не найден"
            )
        return value

    def validate(self, attrs):
        """Комплексная валидация"""
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')

        if date_to and date_from > date_to:
            raise serializers.ValidationError({
                'date_to': 'Дата окончания не может быть раньше даты начала'
            })

        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор профиля пользователя"""

    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    division_name = serializers.CharField(
        source='division_assignment.name',
        read_only=True
    )
    division_type_display = serializers.CharField(
        source='get_division_type_assignment_display',
        read_only=True
    )

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'username', 'email', 'full_name',
            'role', 'role_display',
            'division_assignment', 'division_name',
            'include_child_divisions',
            'division_type_assignment', 'division_type_display',
            'phone', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        """Валидация профиля"""
        role = attrs.get('role', self.instance.role if self.instance else None)
        division_assignment = attrs.get('division_assignment')
        division_type_assignment = attrs.get('division_type_assignment')

        # Для ролей 2, 3, 5, 6 требуется назначение подразделения
        if role in [UserRole.ROLE_2, UserRole.ROLE_3, UserRole.ROLE_5, UserRole.ROLE_6]:
            if not division_assignment and not (self.instance and self.instance.division_assignment):
                raise serializers.ValidationError({
                    'division_assignment': 'Для данной роли требуется указать подразделение'
                })

        # Для роли 5 проверяем соответствие типа подразделения
        if role == UserRole.ROLE_5 and division_type_assignment and division_assignment:
            if division_assignment.division_type != division_type_assignment:
                raise serializers.ValidationError({
                    'division_type_assignment': 'Тип не соответствует назначенному подразделению'
                })

        return attrs


class SecondmentRequestSerializer(serializers.ModelSerializer):
    """Сериализатор запроса на прикомандирование"""

    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    from_division_name = serializers.CharField(source='from_division.name', read_only=True)
    to_division_name = serializers.CharField(source='to_division.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requested_by_name = serializers.CharField(
        source='requested_by.get_full_name',
        read_only=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = SecondmentRequest
        fields = [
            'id', 'employee', 'employee_name',
            'from_division', 'from_division_name',
            'to_division', 'to_division_name',
            'status', 'status_display',
            'date_from', 'date_to', 'reason',
            'requested_by', 'requested_by_name',
            'approved_by', 'approved_by_name',
            'return_requested', 'return_requested_by', 'return_approved_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'requested_by', 'approved_by', 'return_requested_by',
            'return_approved_by', 'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        """Валидация запроса"""
        employee = attrs.get('employee', self.instance.employee if self.instance else None)
        from_division = attrs.get('from_division')
        to_division = attrs.get('to_division')

        # Проверка, что сотрудник принадлежит исходному подразделению
        if employee and from_division:
            if employee.division != from_division:
                raise serializers.ValidationError({
                    'from_division': 'Сотрудник не принадлежит указанному подразделению'
                })

        # Проверка, что подразделения разные
        if from_division and to_division and from_division == to_division:
            raise serializers.ValidationError({
                'to_division': 'Подразделения должны быть разными'
            })

        return attrs


class StaffingUnitSerializer(serializers.ModelSerializer):
    """Сериализатор штатной единицы"""

    division_name = serializers.CharField(source='division.name', read_only=True)
    position_name = serializers.CharField(source='position.name', read_only=True)
    position_level = serializers.IntegerField(source='position.level', read_only=True)
    occupied_count = serializers.IntegerField(read_only=True)
    vacant_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = StaffingUnit
        fields = [
            'id', 'division', 'division_name',
            'position', 'position_name', 'position_level',
            'quantity', 'occupied_count', 'vacant_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_quantity(self, value):
        """Валидация количества"""
        if value < 1:
            raise serializers.ValidationError(
                "Количество должно быть не менее 1"
            )
        return value


class StaffingUnitShortSerializer(serializers.ModelSerializer):
    """Краткий сериализатор штатной единицы"""

    position_name = serializers.CharField(source='position.name')
    vacant_count = serializers.IntegerField()

    class Meta:
        model = StaffingUnit
        fields = ['id', 'position_name', 'quantity', 'vacant_count']


class VacancySerializer(serializers.ModelSerializer):
    """Сериализатор вакансии"""

    division_id = serializers.IntegerField(
        source='staffing_unit.division.id',
        read_only=True
    )
    division_name = serializers.CharField(
        source='staffing_unit.division.name',
        read_only=True
    )
    position_id = serializers.IntegerField(
        source='staffing_unit.position.id',
        read_only=True
    )
    position_name = serializers.CharField(
        source='staffing_unit.position.name',
        read_only=True
    )
    priority_display = serializers.CharField(
        source='get_priority_display',
        read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )
    closed_by_name = serializers.CharField(
        source='closed_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = Vacancy
        fields = [
            'id', 'staffing_unit',
            'division_id', 'division_name',
            'position_id', 'position_name',
            'title', 'description', 'requirements',
            'priority', 'priority_display',
            'is_active', 'created_at', 'created_by', 'created_by_name',
            'closed_at', 'closed_by', 'closed_by_name'
        ]
        read_only_fields = [
            'created_at', 'created_by', 'closed_at', 'closed_by'
        ]


class DivisionStatusUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления статусов подразделения"""

    division_name = serializers.CharField(source='division.name', read_only=True)
    updated_by_name = serializers.CharField(
        source='updated_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = DivisionStatusUpdate
        fields = [
            'id', 'division', 'division_name',
            'update_date', 'is_updated',
            'updated_at', 'updated_by', 'updated_by_name'
        ]
        read_only_fields = ['updated_at', 'updated_by']


class PersonnelReportSerializer(serializers.ModelSerializer):
    """Сериализатор отчета по персоналу"""

    division_name = serializers.CharField(source='division.name', read_only=True)
    report_type_display = serializers.CharField(
        source='get_report_type_display',
        read_only=True
    )
    file_format_display = serializers.CharField(
        source='get_file_format_display',
        read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = PersonnelReport
        fields = [
            'id', 'division', 'division_name',
            'report_date', 'report_type', 'report_type_display',
            'date_from', 'date_to',
            'file', 'file_format', 'file_format_display',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']


class EmployeeTransferLogSerializer(serializers.ModelSerializer):
    """Сериализатор журнала переводов"""

    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    from_division_name = serializers.CharField(
        source='from_division.name',
        read_only=True
    )
    to_division_name = serializers.CharField(
        source='to_division.name',
        read_only=True
    )
    from_position_name = serializers.CharField(
        source='from_position.name',
        read_only=True
    )
    to_position_name = serializers.CharField(
        source='to_position.name',
        read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = EmployeeTransferLog
        fields = [
            'id', 'employee', 'employee_name',
            'from_division', 'from_division_name',
            'to_division', 'to_division_name',
            'from_position', 'from_position_name',
            'to_position', 'to_position_name',
            'transfer_date', 'reason', 'order_number',
            'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']


class EmployeeTransferLogShortSerializer(serializers.ModelSerializer):
    """Краткий сериализатор журнала переводов"""

    from_division_name = serializers.CharField(source='from_division.name')
    to_division_name = serializers.CharField(source='to_division.name')

    class Meta:
        model = EmployeeTransferLog
        fields = [
            'id', 'from_division_name', 'to_division_name',
            'transfer_date', 'reason'
        ]
