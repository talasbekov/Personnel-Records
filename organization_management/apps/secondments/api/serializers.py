from rest_framework import serializers
from organization_management.apps.secondments.models import SecondmentRequest
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division


class SecondmentEmployeeSerializer(serializers.ModelSerializer):
    """Сериализатор для сотрудника в заявках на прикомандирование"""
    full_name = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ['id', 'personnel_number', 'first_name', 'last_name', 'middle_name', 'full_name', 'rank', 'photo_url']

    def get_full_name(self, obj):
        return f"{obj.last_name} {obj.first_name} {obj.middle_name or ''}".strip()

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None


class SecondmentDivisionSerializer(serializers.ModelSerializer):
    """Сериализатор для подразделения в заявках на прикомандирование"""

    class Meta:
        model = Division
        fields = ['id', 'name', 'code', 'division_type']


class SecondmentRequestSerializer(serializers.ModelSerializer):
    employee_detail = SecondmentEmployeeSerializer(source='employee', read_only=True)
    from_division_detail = SecondmentDivisionSerializer(source='from_division', read_only=True)
    to_division_detail = SecondmentDivisionSerializer(source='to_division', read_only=True)

    # Оставляем ID поля для записи
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), write_only=True)
    # from_division определяется автоматически в perform_create, но можно указать вручную
    from_division = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    to_division = serializers.PrimaryKeyRelatedField(queryset=Division.objects.all(), write_only=True)

    class Meta:
        model = SecondmentRequest
        fields = [
            'id',
            'employee', 'employee_detail',
            'from_division', 'from_division_detail',
            'to_division', 'to_division_detail',
            'start_date', 'end_date',
            'reason', 'status',
            'requested_by', 'approved_by', 'rejected_by',
            'rejection_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'approved_by', 'rejected_by', 'created_at', 'updated_at']
