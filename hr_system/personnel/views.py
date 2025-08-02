from rest_framework import viewsets, permissions, status
from .models import (
    Division,
    Position,
    Employee,
    UserProfile,
    EmployeeStatusLog,
    UserRole,
    DivisionStatusUpdate,
    DivisionType,
    SecondmentRequest,
    EmployeeStatusType,
)
from .serializers import (
    DivisionSerializer,
    PositionSerializer,
    EmployeeSerializer,
    UserProfileSerializer,
    MyTokenObtainPairSerializer,
    EmployeeStatusLogSerializer,
    StatusUpdateItemSerializer,
    EmployeeTransferSerializer,
    SecondmentRequestSerializer,
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
    BFS to collect all descendant division IDs. Replace with recursive CTE or tree lib for scale.
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
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except models.ProtectedError:
            return Response(
                {"error": "Cannot delete a division that has employees assigned to it. Please reassign them first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, "profile"):
            return Division.objects.none()
        profile = user.profile

        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return Division.objects.all().prefetch_related("child_divisions")

        assigned_division = profile.division_assignment
        if not assigned_division:
            return Division.objects.none()

        if profile.role == UserRole.ROLE_2:
            descendant_ids = _gather_descendant_ids(assigned_division)
            return Division.objects.filter(id__in=descendant_ids).prefetch_related("child_divisions")

        if profile.role == UserRole.ROLE_5:
            if getattr(profile, "include_child_divisions", False):
                descendant_ids = _gather_descendant_ids(assigned_division)
                return Division.objects.filter(id__in=descendant_ids).prefetch_related("child_divisions")
            else:
                return Division.objects.filter(id=assigned_division.id).prefetch_related("child_divisions")

        if profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]:
            return Division.objects.filter(id=assigned_division.id).prefetch_related("child_divisions")

        return Division.objects.none()

    @action(
        detail=True,
        methods=["post"],
        url_path="update-statuses",
        permission_classes=[IsRole4 | IsRole3 | IsRole6],
    )
    def update_statuses(self, request, pk=None):
        division = self.get_object()
        profile = getattr(request.user, "profile", None)
        if not (
            profile
            and (
                profile.role == UserRole.ROLE_4
                or (
                    profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]
                    and profile.division_assignment == division
                )
            )
        ):
            return Response(
                {"error": "You do not have permission to update statuses for this division."},
                status=status.HTTP_403_FORBIDDEN,
            )

        item_serializer = StatusUpdateItemSerializer(data=request.data, many=True)
        if not item_serializer.is_valid():
            return Response(item_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        status_logs = []
        for item in item_serializer.validated_data:
            employee_id = item.get("employee_id")
            try:
                employee = Employee.objects.get(id=employee_id, division=division)
            except Employee.DoesNotExist:
                return Response(
                    {"error": f"Employee with id {employee_id} not found in this division."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            status_logs.append(
                EmployeeStatusLog(
                    employee=employee,
                    status=item.get("status"),
                    date_from=item.get("date_from"),
                    date_to=item.get("date_to"),
                    comment=item.get("comment", ""),
                    created_by=request.user,
                )
            )

        EmployeeStatusLog.objects.bulk_create(status_logs)
        return Response({"status": "Statuses updated successfully."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):
        """
        Generates and returns the .docx expense report for this division.
        """
        division = self.get_object()
        report_date = datetime.date.today()

        from .services import get_division_statistics, generate_expense_report_docx

        stats = get_division_statistics(division, report_date)
        doc_buffer = generate_expense_report_docx(stats)

        response = HttpResponse(
            doc_buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response["Content-Disposition"] = f'attachment; filename="expense_report_{division.name}_{report_date}.docx"'
        return response

    @action(detail=False, methods=["get"], url_path="status-summary")
    def status_summary(self, request):
        summary_date_str = request.query_params.get("date", datetime.date.today().isoformat())
        summary_date = datetime.date.fromisoformat(summary_date_str)

        queryset = self.get_queryset()

        updates = DivisionStatusUpdate.objects.filter(
            division_id__in=queryset.values_list("id", flat=True),
            update_date=summary_date,
        ).values("division_id", "is_updated")

        updates_map = {item["division_id"]: item["is_updated"] for item in updates}

        division_map = {div.id: div for div in queryset}
        root_divisions = []

        for div in queryset:
            div.summary_data = {
                "id": div.id,
                "name": div.name,
                "division_type": div.division_type,
                "indicator": "UNKNOWN",
                "updated_children": 0,
                "total_children": 0,
                "children": [],
            }
            if div.parent_division_id in division_map:
                parent = division_map[div.parent_division_id]
                if not hasattr(parent, "summary_data"):
                    continue
                parent.summary_data["children"].append(div.summary_data)
            else:
                root_divisions.append(div.summary_data)

        def calculate_indicators(node):
            if not node["children"] and node["division_type"] in [DivisionType.MANAGEMENT, DivisionType.OFFICE]:
                is_updated = updates_map.get(node["id"], False)
                node["indicator"] = "GREEN" if is_updated else "RED"
                return 1, 1 if is_updated else 0

            total_children = 0
            updated_children = 0
            for child in node["children"]:
                child_total, child_updated = calculate_indicators(child)
                total_children += child_total
                updated_children += child_updated

            node["total_children"] = total_children
            node["updated_children"] = updated_children

            if total_children == 0:
                is_updated = updates_map.get(node["id"], False)
                node["indicator"] = "GREEN" if is_updated else "RED"
            elif updated_children == total_children:
                node["indicator"] = "GREEN"
            elif updated_children == 0:
                node["indicator"] = "RED"
            else:
                node["indicator"] = "YELLOW"

            return total_children, updated_children

        for root in root_divisions:
            calculate_indicators(root)

        return Response(root_divisions)


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsRole4 | (IsReadOnly & permissions.IsAuthenticated)]


class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    permission_classes = [IsRole4 | IsRole5 | (IsReadOnly & (IsRole1 | IsRole2 | IsRole3 | IsRole6))]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, "profile"):
            return Employee.objects.none()

        base_queryset = Employee.objects.select_related("position", "division").order_by(
            "position__level", "full_name"
        )

        profile = user.profile

        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return base_queryset.all()

        assigned_division = profile.division_assignment
        if not assigned_division:
            return Employee.objects.none()

        if profile.role == UserRole.ROLE_2 or (profile.role == UserRole.ROLE_5 and getattr(profile, "include_child_divisions", False)):
            descendant_ids = _gather_descendant_ids(assigned_division)
            return base_queryset.filter(division__id__in=descendant_ids)

        if profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]:
            return base_queryset.filter(division__id=assigned_division.id)

        return Employee.objects.none()

    @action(detail=True, methods=["post"], permission_classes=[IsRole4 | IsRole5])
    def terminate(self, request, pk=None):
        employee = self.get_object()
        employee.is_active = False
        employee.fired_date = datetime.date.today()
        employee.save()
        return Response(
            {"status": f"Employee {employee.full_name} has been terminated."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsRole4 | IsRole5])
    def transfer(self, request, pk=None):
        employee = self.get_object()
        serializer = EmployeeTransferSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_division_id = serializer.validated_data["new_division_id"]
        try:
            new_division = Division.objects.get(id=new_division_id)
        except Division.DoesNotExist:
            return Response({"error": "Target division does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        profile = request.user.profile
        if profile.role == UserRole.ROLE_5:
            scope_checker = IsRole5()
            if not scope_checker.has_object_permission(request, self, employee.division) or not scope_checker.has_object_permission(
                request, self, new_division
            ):
                return Response(
                    {"error": "You can only transfer employees within your assigned division scope."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        employee.division = new_division
        employee.save()
        return Response(
            {"status": f"Employee {employee.full_name} transferred to {new_division.name}."},
            status=status.HTTP_200_OK,
        )


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all().select_related("user", "division_assignment")
    serializer_class = UserProfileSerializer
    permission_classes = [IsRole4]


class MyTokenObtainPairView(OriginalTokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class EmployeeStatusLogViewSet(viewsets.ModelViewSet):
    queryset = EmployeeStatusLog.objects.all()
    serializer_class = EmployeeStatusLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


class SecondmentRequestViewSet(viewsets.ModelViewSet):
    queryset = SecondmentRequest.objects.all().select_related(
        "employee__position", "from_division", "to_division", "requested_by", "approved_by"
    )
    serializer_class = SecondmentRequestSerializer
    permission_classes = [IsRole4 | IsRole5]

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"], permission_classes=[IsRole4 | IsRole5])
    def approve(self, request, pk=None):
        instance = self.get_object()
        if instance.status != "PENDING":
            return Response({"error": "Only pending requests can be approved."}, status=status.HTTP_400_BAD_REQUEST)

        instance.status = "APPROVED"
        instance.approved_by = request.user
        instance.save()

        EmployeeStatusLog.objects.create(
            employee=instance.employee,
            status=EmployeeStatusType.SECONDED_OUT,
            date_from=instance.date_from,
            date_to=instance.date_to,
            comment=f"Seconded to {instance.to_division.name}",
            secondment_division=instance.to_division,
            created_by=request.user,
        )

        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"], permission_classes=[IsRole4 | IsRole5])
    def reject(self, request, pk=None):
        instance = self.get_object()
        if instance.status != "PENDING":
            return Response({"error": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        instance.status = "REJECTED"
        instance.save()
        return Response(self.get_serializer(instance).data)
