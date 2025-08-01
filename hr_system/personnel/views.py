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
from django.db import models
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse


def _gather_descendant_ids(root_division):
    """
    Простой BFS для сбора всех потомков. Можно заменить на рекурсивный CTE
    или использовать специализированную библиотеку (django-mptt/treebeard)
    для лучшей производительности на глубоких деревьях.
    """
    descendant_ids = [root_division.id]
    queue = [root_division]
    visited = {root_division.id}
    while queue:
        current = queue.pop(0)
        for child in current.child_divisions.all():
            if child.id not in visited:
                descendant_ids.append(child.id)
                visited.add(child.id)
                queue.append(child)
    return descendant_ids


class DivisionViewSet(viewsets.ModelViewSet):
    serializer_class = DivisionSerializer
    permission_classes = [IsRole4 | (IsReadOnly & (IsRole1 | IsRole2 | IsRole3 | IsRole5 | IsRole6))]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.child_divisions.exists():
            return Response(
                {"error": "Cannot delete a division that has child divisions. Please reassign children first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except models.ProtectedError:
            return Response(
                {"error": "Cannot delete a division that has employees assigned to it. Please reassign them first."},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'profile'):
            return Division.objects.none()
        profile = user.profile

        # ROLE_1 и ROLE_4 видят все
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return Division.objects.all().prefetch_related("child_divisions")

        assigned_division = profile.division_assignment
        if not assigned_division:
            return Division.objects.none()

        # ROLE_2 всегда включает потомков
        if profile.role == UserRole.ROLE_2:
            descendant_ids = _gather_descendant_ids(assigned_division)
            return Division.objects.filter(id__in=descendant_ids).prefetch_related("child_divisions")

        # ROLE_5 — только если флаг
        if profile.role == UserRole.ROLE_5:
            if getattr(profile, 'include_child_divisions', False):
                descendant_ids = _gather_descendant_ids(assigned_division)
                return Division.objects.filter(id__in=descendant_ids).prefetch_related("child_divisions")
            else:
                return Division.objects.filter(id=assigned_division.id).prefetch_related("child_divisions")

        # ROLE_3 и ROLE_6 — только своё подразделение
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
        response = HttpResponse(
            doc_buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
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

        base_queryset = Employee.objects.select_related("position", "division").order_by(
            'position__level', 'full_name'
        )

        profile = user.profile

        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return base_queryset.all()

        assigned_division = profile.division_assignment
        if not assigned_division:
            return Employee.objects.none()

        # ROLE_2: всегда включает дочерние подразделения
        # ROLE_5: включает только если include_child_divisions == True
        if profile.role == UserRole.ROLE_2 or (profile.role == UserRole.ROLE_5 and getattr(profile, 'include_child_divisions', False)):
            descendant_ids = _gather_descendant_ids(assigned_division)
            return base_queryset.filter(division__id__in=descendant_ids)

        # ROLE_3 и ROLE_6 — только своё подразделение
        if profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]:
            return base_queryset.filter(division__id=assigned_division.id)

        return Employee.objects.none()


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all().select_related("user", "division_assignment")
    serializer_class = UserProfileSerializer
    permission_classes = [IsRole4]


class MyTokenObtainPairView(OriginalTokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
