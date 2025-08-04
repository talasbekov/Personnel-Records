"""
Serializers for the personnel application.

This file is adapted from the original repository and includes several
enhancements:

* ``UserProfileSerializer`` now exposes the ``include_child_divisions``
  and ``division_type_assignment`` fields so that administrators can
  assign these properties to Role‑5 users.  Without these fields the
  API could not set or update them, which was one of the shortcomings
  identified in the audit.

* ``DivisionSerializer`` includes the ``hierarchy_variant`` field from
  the ``Division`` model.  This allows clients to understand how a
  particular division participates in the overall organisational
  structure.

All original validation logic has been retained.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Q
from .models import (
    Division,
    Position,
    Employee,
    UserProfile,
    EmployeeStatusLog,
    DivisionType,
    UserRole,
    EmployeeStatusType,
    SecondmentRequest,
    StaffingUnit,
    Vacancy,
)
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class DivisionSerializer(serializers.ModelSerializer):
    division_type_display = serializers.CharField(
        source="get_division_type_display", read_only=True
    )
    parent_division_id = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(),
        source="parent_division",
        allow_null=True,
        required=False,
        write_only=True,
    )
    children = serializers.SerializerMethodField(read_only=True)
    hierarchy_variant = serializers.CharField(read_only=True)

    class Meta:
        model = Division
        fields = [
            "id",
            "name",
            "parent_division_id",
            "division_type",
            "division_type_display",
            "hierarchy_variant",
            "children",
        ]

    def get_children(self, obj):
        if hasattr(obj, "filtered_children_for_api"):
            children_queryset = obj.filtered_children_for_api
        else:
            children_queryset = obj.child_divisions.all()
        serializer = self.__class__(children_queryset, many=True, context=self.context)
        return serializer.data

    def validate(self, data):
        """
        Check for cyclical dependencies when assigning a parent division.
        """
        instance = self.instance
        parent = data.get("parent_division")
        if not parent:
            return data  # No parent, no cycle
        # On create, instance is None. On update, it's the object being updated.
        if instance and parent == instance:
            raise serializers.ValidationError("A division cannot be its own parent.")
        # Traverse up from the parent to see if we hit the instance
        current = parent
        while current:
            if instance and current == instance:
                raise serializers.ValidationError(
                    "A division cannot have one of its children as its parent."
                )
            current = current.parent_division
        return data


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "name", "level"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Display user details
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True
    )
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    division_assignment_id = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(),
        source="division_assignment",
        allow_null=True,
        required=False,
    )
    include_child_divisions = serializers.BooleanField(required=False)
    division_type_assignment = serializers.ChoiceField(
        choices=DivisionType.choices, allow_null=True, required=False
    )

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "user_id",
            "role",
            "role_display",
            "division_assignment_id",
            "include_child_divisions",
            "division_type_assignment",
        ]


class EmployeeSerializer(serializers.ModelSerializer):
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(), source="position"
    )
    division_id = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(), source="division"
    )
    position = PositionSerializer(read_only=True)
    division = DivisionSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "full_name",
            "photo",
            "position_id",
            "position",
            "division_id",
            "division",
        ]

    def validate(self, data):
        user = self.context["request"].user
        if not user.is_authenticated or not hasattr(user, "profile"):
            raise serializers.ValidationError("User profile not found.")
        profile = user.profile
        if profile.role == UserRole.ROLE_5:
            assigned_division = profile.division_assignment
            target_division = data.get("division")
            if not assigned_division or not target_division:
                raise serializers.ValidationError(
                    "Assigned division or target division is missing."
                )
            # Check if target_division is within the scope of assigned_division
            current = target_division
            within_scope = False
            while current:
                if current == assigned_division:
                    within_scope = True
                    break
                current = current.parent_division
            if not within_scope:
                raise serializers.ValidationError(
                    "You do not have permission to create an employee in this division."
                )
            # Enforce division type assignment if set
            division_type_assignment = getattr(profile, "division_type_assignment", None)
            if division_type_assignment and target_division.division_type != division_type_assignment:
                raise serializers.ValidationError(
                    "You do not have permission to create an employee in a division of this type."
                )
        return data


class EmployeeStatusLogSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source="employee"
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = EmployeeStatusLog
        fields = [
            "id",
            "employee_id",
            "status",
            "status_display",
            "date_from",
            "date_to",
            "comment",
            "secondment_division",
            "created_at",
            "created_by",
        ]
        read_only_fields = ("created_at", "created_by")

    def validate(self, data):
        """
        Prevent overlapping status intervals for the same employee and
        conflicting status types.  Statuses such as ``SECONDED_OUT`` and
        ``SECONDED_IN`` can coexist with others, but other statuses must
        not overlap.
        """
        employee = data.get("employee")
        new_status = data.get("status")
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if not all([employee, new_status, date_from]):
            # Not enough data to validate; other validators will catch this.
            return data
        # Define statuses that can coexist with others.
        COEXISTING_STATUSES = {EmployeeStatusType.SECONDED_OUT, EmployeeStatusType.SECONDED_IN}
        # If the new status can coexist, no need to check for conflicts.
        if new_status in COEXISTING_STATUSES:
            return data
        # Find existing statuses that overlap with the new date range.
        # An overlap occurs if (StartA <= EndB) and (EndA >= StartB)
        overlapping_statuses = EmployeeStatusLog.objects.filter(
            employee=employee,
            # Exclude statuses that can coexist.
            status__in=[s for s in EmployeeStatusType if s not in COEXISTING_STATUSES],
            date_from__lte=date_to if date_to else date_from,
        ).filter(Q(date_to__gte=date_from) | Q(date_to__isnull=True))
        # If updating an existing instance, exclude it from the check.
        if self.instance:
            overlapping_statuses = overlapping_statuses.exclude(pk=self.instance.pk)
        if overlapping_statuses.exists():
            conflict = overlapping_statuses.first()
            raise serializers.ValidationError(
                f"The proposed status conflicts with an existing status ('{conflict.get_status_display()}') "
                f"from {conflict.date_from} to {conflict.date_to or 'ongoing'}."
            )
        # Ensure date_to is not earlier than date_from
        if date_to and date_to < date_from:
            raise serializers.ValidationError("The end date cannot be earlier than the start date.")
        return data

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class StaffingUnitSerializer(serializers.ModelSerializer):
    division_id = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(), source="division"
    )
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(), source="position"
    )
    division = DivisionSerializer(read_only=True)
    position = PositionSerializer(read_only=True)

    class Meta:
        model = StaffingUnit
        fields = [
            "id",
            "division",
            "division_id",
            "position",
            "position_id",
            "quantity",
            "occupied_count",
            "vacant_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["occupied_count", "vacant_count", "created_at", "updated_at"]


class VacancySerializer(serializers.ModelSerializer):
    staffing_unit_id = serializers.PrimaryKeyRelatedField(
        queryset=StaffingUnit.objects.all(), source="staffing_unit"
    )
    staffing_unit = StaffingUnitSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    closed_by = UserSerializer(read_only=True)

    class Meta:
        model = Vacancy
        fields = [
            "id",
            "staffing_unit",
            "staffing_unit_id",
            "title",
            "description",
            "requirements",
            "priority",
            "is_active",
            "created_at",
            "created_by",
            "closed_at",
            "closed_by",
        ]
        read_only_fields = ["created_at", "created_by", "closed_at", "closed_by"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class StatusUpdateItemSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=EmployeeStatusType.choices)
    date_from = serializers.DateField()
    date_to = serializers.DateField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class EmployeeTransferSerializer(serializers.Serializer):
    new_division_id = serializers.IntegerField()
    def validate_new_division_id(self, value):
        try:
            Division.objects.get(id=value)
        except Division.DoesNotExist:
            raise serializers.ValidationError("Division with this ID does not exist.")
        return value


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        try:
            profile = user.profile
            token["role"] = profile.role
            token["division_id"] = (
                profile.division_assignment.id if profile.division_assignment else None
            )
        except User.profile.RelatedObjectDoesNotExist:
            # Record a log entry so that missing profiles can be spotted during
            # development.  These prints go to standard output rather than
            # server logs.
            print(
                f"JWT_CLAIM_LOG: User {user.username} has no profile. Claims 'role'/'division_id' are null."
            )
            token["role"] = None
            token["division_id"] = None
        except AttributeError as e:
            print(
                f"JWT_CLAIM_LOG: User {user.username} profile missing attribute: {e}. Claims 'role'/'division_id' are null."
            )
            token["role"] = None
            token["division_id"] = None
        return token


class SecondmentRequestSerializer(serializers.ModelSerializer):
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source="employee"
    )
    to_division_id = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(), source="to_division"
    )
    employee = EmployeeSerializer(read_only=True)
    from_division = DivisionSerializer(read_only=True)
    to_division = DivisionSerializer(read_only=True)
    requested_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

    class Meta:
        model = SecondmentRequest
        fields = [
            "id",
            "employee",
            "employee_id",
            "from_division",
            "to_division",
            "to_division_id",
            "status",
            "date_from",
            "date_to",
            "reason",
            "requested_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "from_division",
            "requested_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        employee = validated_data["employee"]
        validated_data["from_division"] = employee.division
        validated_data["requested_by"] = self.context["request"].user
        return super().create(validated_data)
