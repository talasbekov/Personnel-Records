"""
Сериализаторы для API управления статусами сотрудников
"""
from rest_framework import serializers
from organization_management.apps.statuses.models import (
    EmployeeStatus,
    StatusChangeHistory,
    StatusDocument
)
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division


class EmployeeBasicSerializer(serializers.ModelSerializer):
    """Базовый сериализатор сотрудника для вложенного представления"""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ['id', 'personnel_number', 'last_name', 'first_name', 'middle_name', 'full_name']

    def get_full_name(self, obj: Employee) -> str:
        return f"{obj.last_name} {obj.first_name} {obj.middle_name}".strip()


class DivisionBasicSerializer(serializers.ModelSerializer):
    """Базовый сериализатор подразделения для вложенного представления"""

    class Meta:
        model = Division
        fields = ['id', 'name', 'code']


class StatusChangeHistorySerializer(serializers.ModelSerializer):
    """Сериализатор истории изменений статуса"""
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StatusChangeHistory
        fields = [
            'id', 'change_type', 'change_type_display', 'old_value', 'new_value',
            'comment', 'changed_by', 'changed_by_name', 'changed_at'
        ]
        read_only_fields = ['id', 'changed_at']

    def get_changed_by_name(self, obj: StatusChangeHistory) -> str:
        if obj.changed_by:
            return f"{obj.changed_by.first_name} {obj.changed_by.last_name}".strip() or obj.changed_by.username
        return None


class StatusDocumentSerializer(serializers.ModelSerializer):
    """Сериализатор документов статуса"""
    uploaded_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = StatusDocument
        fields = [
            'id', 'status', 'title', 'file', 'file_url', 'description',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']

    def get_uploaded_by_name(self, obj: StatusDocument) -> str:
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.username
        return None

    def get_file_url(self, obj: StatusDocument) -> str:
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class EmployeeStatusSerializer(serializers.ModelSerializer):
    """
    Основной сериализатор для статуса сотрудника
    """
    employee_data = EmployeeBasicSerializer(source='employee', read_only=True)
    related_division_data = DivisionBasicSerializer(source='related_division', read_only=True)
    status_type_display = serializers.CharField(source='get_status_type_display', read_only=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    effective_end_date = serializers.DateField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_planned = serializers.BooleanField(read_only=True)

    class Meta:
        model = EmployeeStatus
        fields = [
            'id', 'employee', 'employee_data', 'status_type', 'status_type_display',
            'state', 'state_display', 'start_date', 'end_date', 'actual_end_date',
            'effective_end_date', 'comment', 'early_termination_reason',
            'related_division', 'related_division_data', 'location',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'is_notified', 'auto_applied', 'is_active', 'is_planned'
        ]
        read_only_fields = [
            'id', 'state', 'created_at', 'updated_at', 'is_notified',
            'auto_applied', 'actual_end_date', 'early_termination_reason'
        ]

    def get_created_by_name(self, obj: EmployeeStatus) -> str:
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None

    def validate(self, attrs):
        """Валидация данных с помощью метода clean модели"""
        instance = self.instance or EmployeeStatus()

        # Копируем атрибуты из attrs
        for key, value in attrs.items():
            setattr(instance, key, value)

        # Для partial update заполняем недостающие поля из instance
        if self.instance:
            for field in self.Meta.model._meta.fields:
                if field.name not in attrs and hasattr(self.instance, field.name):
                    setattr(instance, field.name, getattr(self.instance, field.name))

        # Вызываем clean() модели для валидации
        instance.clean()

        return attrs


class EmployeeStatusDetailSerializer(EmployeeStatusSerializer):
    """Детальный сериализатор статуса с историей изменений и документами"""
    change_history = StatusChangeHistorySerializer(many=True, read_only=True)
    documents = StatusDocumentSerializer(many=True, read_only=True)

    class Meta(EmployeeStatusSerializer.Meta):
        fields = EmployeeStatusSerializer.Meta.fields + ['change_history', 'documents']


class EmployeeStatusCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания статуса"""

    class Meta:
        model = EmployeeStatus
        fields = [
            'employee', 'status_type', 'start_date', 'end_date',
            'comment', 'location', 'related_division'
        ]

    def validate(self, attrs):
        """Валидация данных"""
        instance = EmployeeStatus(**attrs)
        instance.clean()
        return attrs


class EmployeeStatusExtendSerializer(serializers.Serializer):
    """Сериализатор для продления статуса"""
    new_end_date = serializers.DateField(required=True)


class EmployeeStatusTerminateSerializer(serializers.Serializer):
    """Сериализатор для досрочного завершения статуса"""
    termination_date = serializers.DateField(required=True)
    reason = serializers.CharField(required=True, min_length=1)


class EmployeeStatusCancelSerializer(serializers.Serializer):
    """Сериализатор для отмены запланированного статуса"""
    reason = serializers.CharField(required=True, min_length=1)


class StatusDocumentUploadSerializer(serializers.ModelSerializer):
    """Сериализатор для загрузки документа"""

    class Meta:
        model = StatusDocument
        fields = ['title', 'file', 'description']

    def validate_file(self, value):
        """Валидация файла"""
        # Ограничение размера файла (10 МБ)
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("Размер файла не должен превышать 10 МБ.")

        return value


class DivisionHeadcountSerializer(serializers.Serializer):
    """Сериализатор для расхода подразделения"""
    division_id = serializers.IntegerField()
    date = serializers.DateField()
    total_count = serializers.IntegerField()
    in_service_count = serializers.IntegerField()
    absent_count = serializers.IntegerField()
    absent_by_type = serializers.DictField()


class AbsenceStatisticsSerializer(serializers.Serializer):
    """Сериализатор для статистики по отсутствиям"""
    period = serializers.DictField()
    division_id = serializers.IntegerField(allow_null=True)
    total_absences = serializers.IntegerField()
    by_type = serializers.DictField()


class BulkStatusPlanSerializer(serializers.Serializer):
    """Сериализатор для массового планирования статусов"""
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    status_type = serializers.ChoiceField(choices=EmployeeStatus.StatusType.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    comment = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    related_division = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        """Валидация данных"""
        if attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError({
                'end_date': 'Дата окончания не может быть раньше даты начала.'
            })
        return attrs
