"""
Serializers for the personnel application.

This module defines serializers for API endpoints working with the
``Division`` model.  A simple ``DivisionSerializer`` is provided for
listing and creating divisions.  For more complex nested
representations or validation logic, extend these classes as needed.
"""

from rest_framework import serializers

try:
    from .models import Division
except Exception:  # pragma: no cover
    Division = None  # type: ignore

from .models import (
    Position, Employee, UserProfile,
    SecondmentRequest, EmployeeStatusLog,
    StaffingUnit, Vacancy
)

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class SecondmentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecondmentRequest
        fields = '__all__'


class EmployeeStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeStatusLog
        fields = '__all__'


class StaffingUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffingUnit
        fields = '__all__'


class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'


class DivisionSerializer(serializers.ModelSerializer):
    """Serializer for the Division model.

    Exposes the primary fields necessary for basic CRUD operations on
    divisions, including the parent relationship and hierarchy variant.
    """

    class Meta:
        model = Division
        # Only basic fields are included; extend this list as required
        fields = [
            "id",
            "name",
            "division_type",
            "parent_division",
            "hierarchy_variant",
        ]
        extra_kwargs = {
            "parent_division": {"allow_null": True, "required": False},
            "hierarchy_variant": {"allow_null": True, "required": False},
        }