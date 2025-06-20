from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Division, Position, Employee, UserProfile, EmployeeStatusLog, DivisionType, UserRole
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer # Added by subtask

class DivisionSerializer(serializers.ModelSerializer):
    division_type_display = serializers.CharField(source='get_division_type_display', read_only=True)
    parent_division_id = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(),
        source='parent_division',
        allow_null=True,
        required=False,
        write_only=True
    )
    children = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Division
        fields = ['id', 'name', 'parent_division_id', 'division_type', 'division_type_display', 'children']

    def get_children(self, obj):
        if hasattr(obj, 'filtered_children_for_api'):
            children_queryset = obj.filtered_children_for_api
        else:
            children_queryset = obj.child_divisions.all()

        serializer = self.__class__(children_queryset, many=True, context=self.context)
        return serializer.data
class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'name', 'level']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) # Display user details
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    division_assignment_id = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(),
        source='division_assignment',
        allow_null=True,
        required=False
    )


    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'user_id', 'role', 'role_display', 'division_assignment_id']


class EmployeeSerializer(serializers.ModelSerializer):
    position_id = serializers.PrimaryKeyRelatedField(queryset=Position.objects.all(), source='position')
    division_id = serializers.PrimaryKeyRelatedField(queryset=Division.objects.all(), source='division')
    # user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', allow_null=True, required=False)

    # To make position and division more readable in GET requests
    position = PositionSerializer(read_only=True)
    division = DivisionSerializer(read_only=True)
    # user = UserSerializer(read_only=True, allow_null=True)


    class Meta:
        model = Employee
        fields = [
            'id', 'full_name', 'photo',
            'position_id', 'position',
            'division_id', 'division',
            # 'user_id', 'user'
        ]
        # depth = 1 # Alternative to nested serializers for read-only

# EmployeeStatusLog might be handled by specific actions rather than generic CRUD
# class EmployeeStatusLogSerializer(serializers.ModelSerializer):
#     employee_id = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), source='employee')
#     status_display = serializers.CharField(source='get_status_display', read_only=True)
#     class Meta:
#         model = EmployeeStatusLog
#         fields = ['id', 'employee_id', 'status', 'status_display', 'date_from', 'date_to', 'comment', 'secondment_division']

# Custom Token Serializer for JWT claims (appended by subtask)
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        try:
            profile = user.profile
            token['role'] = profile.role
            token['division_id'] = profile.division_assignment.id if profile.division_assignment else None
        except User.profile.RelatedObjectDoesNotExist:
            # This print statement might go to subtask logs, not server logs
            print(f"JWT_CLAIM_LOG: User {user.username} has no profile. Claims 'role'/'division_id' are null.")
            token['role'] = None
            token['division_id'] = None
        except AttributeError as e:
            print(f"JWT_CLAIM_LOG: User {user.username} profile missing attribute: {e}. Claims 'role'/'division_id' are null.")
            token['role'] = None
            token['division_id'] = None
        return token
