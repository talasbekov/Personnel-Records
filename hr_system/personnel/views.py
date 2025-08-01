from rest_framework import viewsets, permissions, status
from .models import Division, Position, Employee, UserProfile, EmployeeStatusLog, UserRole
from .serializers import (
    DivisionSerializer,
    PositionSerializer,
    EmployeeSerializer,
    UserProfileSerializer,
    MyTokenObtainPairSerializer,
    EmployeeStatusLogSerializer,
    StatusUpdateItemSerializer
)
from rest_framework_simplejwt.views import TokenObtainPairView as OriginalTokenObtainPairView
from .permissions import IsRole4, IsRole1, IsRole2, IsRole3, IsRole5, IsRole6, IsReadOnly
import datetime
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse

class DivisionViewSet(viewsets.ModelViewSet):
    serializer_class = DivisionSerializer
    permission_classes = [IsRole4 | (IsReadOnly & (IsRole1 | IsRole2 | IsRole3 | IsRole5 | IsRole6))]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            return Division.objects.none()
        profile = user.profile
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return Division.objects.all().prefetch_related("child_divisions")
        assigned_division = profile.division_assignment
        if not assigned_division:
            return Division.objects.none()
        if profile.role in [UserRole.ROLE_2, UserRole.ROLE_5]:
            descendant_ids = [assigned_division.id]
            # Fetch descendants only if the flag is set for Role 5, or always for Role 2
            fetch_children = (profile.role == UserRole.ROLE_2) or \
                             (profile.role == UserRole.ROLE_5 and profile.include_child_divisions)

            if fetch_children:
                queue = [assigned_division]
                visited = {assigned_division.id}
                while queue:
                    current_division = queue.pop(0)
                    for child in current_division.child_divisions.all():
                        if child.id not in visited:
                            descendant_ids.append(child.id)
                            visited.add(child.id)
                            queue.append(child)

            return Division.objects.filter(id__in=descendant_ids).prefetch_related("child_divisions")
        if profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]:
            return Division.objects.filter(id=assigned_division.id).prefetch_related("child_divisions")
        return Division.objects.none()

    @action(detail=True, methods=['post'], url_path='update-statuses', permission_classes=[IsRole4 | IsRole3 | IsRole6])
    def update_statuses(self, request, pk=None):
        division = self.get_object()
        profile = getattr(request.user, 'profile', None)

        if not (profile and (profile.role == UserRole.ROLE_4 or (profile.role in [UserRole.ROLE_3, UserRole.ROLE_6] and profile.division_assignment == division))):
             return Response({'error': 'You do not have permission to update statuses for this division.'}, status=status.HTTP_403_FORBIDDEN)

        item_serializer = StatusUpdateItemSerializer(data=request.data, many=True)
        if not item_serializer.is_valid():
            return Response(item_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        status_logs = []
        for item in item_serializer.validated_data:
            employee_id = item.get('employee_id')
            try:
                employee = Employee.objects.get(id=employee_id, division=division)
            except Employee.DoesNotExist:
                return Response({'error': f'Employee with id {employee_id} not found in this division.'}, status=status.HTTP_400_BAD_REQUEST)

            status_logs.append(
                EmployeeStatusLog(
                    employee=employee,
                    status=item.get('status'),
                    date_from=item.get('date_from'),
                    date_to=item.get('date_to'),
                    comment=item.get('comment', ''),
                    created_by=request.user
                )
            )

        EmployeeStatusLog.objects.bulk_create(status_logs)
        return Response({'status': 'Statuses updated successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, pk=None):
        """
        Generates and returns the .docx expense report for this division.
        """
        division = self.get_object()

        # For now, we use today's date. This could be a query param.
        report_date = datetime.date.today()

        # 1. Get statistics using the service
        from .services import get_division_statistics, generate_expense_report_docx
        stats = get_division_statistics(division, report_date)

        # 2. Generate the .docx file in memory
        doc_buffer = generate_expense_report_docx(stats)

        # 3. Return the file in the response
        response = HttpResponse(doc_buffer.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="expense_report_{division.name}_{report_date}.docx"'
        return response


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsRole4 | (IsReadOnly & permissions.IsAuthenticated)]

class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    permission_classes = [IsRole4 | IsRole5 | (IsReadOnly & (IsRole1 | IsRole2 | IsRole3 | IsRole6))]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            return Employee.objects.none()

        # Base queryset with ordering
        base_queryset = Employee.objects.select_related("position", "division").order_by('position__level', 'full_name')

        profile = user.profile
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return base_queryset.all()

        assigned_division = profile.division_assignment
        if not assigned_division:
            return Employee.objects.none()

        descendant_ids = [assigned_division.id]
        # For roles 2 and 5, fetch descendants only if the flag is set
        fetch_children = (profile.role == UserRole.ROLE_2) or \
                         (profile.role == UserRole.ROLE_5 and profile.include_child_divisions)

        if fetch_children:
            # A more efficient way to get all descendant IDs
            queue = [assigned_division]
            visited = {assigned_division.id}
            while queue:
                current_division = queue.pop(0)
                # We need to fetch children for the current division in the queue
                # Note: This can still be slow for very deep hierarchies.
                # A recursive CTE would be the most performant solution.
                for child in current_division.child_divisions.all():
                    if child.id not in visited:
                        descendant_ids.append(child.id)
                        visited.add(child.id)
                        queue.append(child)

        return base_queryset.filter(division__id__in=descendant_ids)

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all().select_related("user", "division_assignment")
    serializer_class = UserProfileSerializer
    permission_classes = [IsRole4]

class MyTokenObtainPairView(OriginalTokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
