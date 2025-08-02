from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Division,
    Position,
    Employee,
    UserProfile,
    EmployeeStatusLog,
    DivisionType,
    UserRole,
    EmployeeStatusType,
)
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
)  # Added by subtask


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

    class Meta:
        model = Division
        fields = [
            "id",
            "name",
            "parent_division_id",
            "division_type",
            "division_type_display",
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
        Check for cyclical dependencies.
        """
        instance = self.instance
        parent = data.get('parent_division')

        if not parent:
            return data # No parent, no cycle

        # On create, instance is None. On update, it's the object being updated.
        if instance and parent == instance:
            raise serializers.ValidationError("A division cannot be its own parent.")

        # Traverse up from the parent to see if we hit the instance
        current = parent
        while current:
            if instance and current == instance:
                raise serializers.ValidationError("A division cannot have one of its children as its parent.")
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

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "user_id",
            "role",
            "role_display",
            "division_assignment_id",
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
        user = self.context['request'].user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            raise serializers.ValidationError("User profile not found.")

        profile = user.profile
        if profile.role == UserRole.ROLE_5:
            assigned_division = profile.division_assignment
            target_division = data.get('division')

            if not assigned_division or not target_division:
                raise serializers.ValidationError("Assigned division or target division is missing.")

            # Check if target_division is within the scope of assigned_division
            current = target_division
            while current:
                if current == assigned_division:
                    return data
                current = current.parent_division

            raise serializers.ValidationError("You do not have permission to create an employee in this division.")

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

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class StatusUpdateItemSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=EmployeeStatusType.choices)
    date_from = serializers.DateField()
    date_to = serializers.DateField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)


# Custom Token Serializer for JWT claims (appended by subtask)
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
            # This print statement might go to subtask logs, not server logs
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
