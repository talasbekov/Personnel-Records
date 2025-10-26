from rest_framework import serializers
from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.api.serializers import EmployeeSerializer


class DivisionSerializer(serializers.ModelSerializer):
    """Base serializer for divisions."""

    parent_division_name = serializers.CharField(
        source='parent_division.name',
        read_only=True
    )
    division_type_display = serializers.CharField(
        source='get_division_type_display',
        read_only=True
    )
    head_position_name = serializers.CharField(
        source='head_position.name',
        read_only=True
    )
    employee_count = serializers.SerializerMethodField()
    child_divisions_count = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    employees = serializers.SerializerMethodField()

    class Meta:
        model = Division
        fields = [
            'id', 'name', 'code', 'division_type', 'division_type_display',
            'parent_division', 'parent_division_name',
            'description', 'contact_info', 'head_position', 'head_position_name',
            'employee_count', 'child_divisions_count',
            'children', 'employees'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'hierarchy_variant': {'required': False},
        }

    def get_employee_count(self, obj):
        return obj.employees.filter(is_active=True).count()

    def get_employees(self, obj):
        if obj.child_divisions.exists():
            return []
        active = obj.employees.filter(is_active=True)
        return EmployeeSerializer(active, many=True).data

    def get_child_divisions_count(self, obj):
        return obj.child_divisions.count()

    def get_children(self, obj):
        children = obj.child_divisions.all()
        return DivisionSerializer(children, many=True, context=self.context).data


class DivisionDetailSerializer(DivisionSerializer):
    """Detailed serializer for a division."""

    staffing_units = serializers.SerializerMethodField()
    active_vacancies = serializers.SerializerMethodField()
    status_indicator = serializers.SerializerMethodField()

    class Meta(DivisionSerializer.Meta):
        fields = DivisionSerializer.Meta.fields + [
            'staffing_units', 'active_vacancies', 'status_indicator'
        ]

    def get_staffing_units(self, obj):
        from organization_management.apps.employees.api.serializers import StaffingUnitShortSerializer
        units = obj.staffing_units.select_related('position')
        return StaffingUnitShortSerializer(units, many=True).data

    def get_active_vacancies(self, obj):
        from organization_management.apps.employees.models import Vacancy
        vacancies = Vacancy.objects.filter(
            staffing_unit__division=obj,
            is_active=True
        ).count()
        return vacancies

    def get_status_indicator(self, obj):
        from organization_management.apps.statuses.models import DivisionStatusUpdate
        from django.utils import timezone
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
    """Serializer for the division tree view."""

    children = serializers.SerializerMethodField()

    class Meta:
        model = Division
        fields = ['id', 'name', 'code', 'division_type', 'children']

    def get_children(self, obj):
        children = obj.child_divisions.all()
        return DivisionTreeSerializer(children, many=True).data
