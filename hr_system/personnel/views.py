"""
ViewSets and API endpoints for the personnel application.

This module mirrors the structure of the original project but includes a
number of improvements and new actions:

* Multi‑day status planning: the ``update_statuses`` action now
  supports ``date_to`` and creates a single log covering the entire
  period.  It also records ``DivisionStatusUpdate`` entries for every
  date between ``date_from`` and ``date_to`` (inclusive) to drive the
  status indicators on the dashboard.

* Status update gating for reports: both the daily ``report`` and
  ``periodic_report`` actions now refuse to generate a document if
  there are outstanding divisions whose statuses have not been
  updated.  This ensures reports reflect the latest available data.

* Report persistence: generated reports are stored via the
  ``PersonnelReport`` model.  A temporary in‑memory file is attached
  before the response is sent to the client.

* New actions ``return_from_secondment`` on ``SecondmentRequestViewSet`` and
  ``close`` on ``VacancyViewSet`` to handle the full lifecycle of
  secondments and vacancies.

* Enhanced Role‑5 query logic: ``DivisionViewSet.get_queryset`` now
  honours the ``division_type_assignment`` and ``include_child_divisions``
  flags on the user's profile, providing tighter control over what
  divisions a HR administrator can see.

* Optional caching: ``list`` actions on Division, Position, Employee and
  StaffingUnit viewsets are decorated with ``cache_page`` to reduce
  database load.  The cache timeout can be tuned via the settings.

The remainder of the code is unchanged to preserve existing behaviour
where no issues were identified.
"""

import datetime
from collections import defaultdict

from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.conf import settings
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView as OriginalTokenObtainPairView

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
    StaffingUnit,
    Vacancy,
    PersonnelReport,
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
    StaffingUnitSerializer,
    VacancySerializer,
)
from .permissions import IsRole4, IsRole1, IsRole2, IsRole3, IsRole5, IsRole6, IsReadOnly
from .services import (
    get_division_statistics,
    generate_expense_report_xlsx,
    generate_expense_report_pdf,
    generate_periodic_report_xlsx,
    generate_periodic_report_pdf,
    generate_detailed_report_docx,
    generate_detailed_periodic_report_docx,
)


def _gather_descendant_ids(root_division):
    """
    Breadth‑first traversal to collect all descendant division IDs.
    Replace with a recursive CTE or tree utility for large hierarchies.
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

    @method_decorator(cache_page(settings.CACHE_TIMEOUT))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Prevent deletion if the division has children
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
        # Role 1 and 4 see everything
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return Division.objects.all().prefetch_related("child_divisions")
        assigned_division = profile.division_assignment
        if not assigned_division:
            return Division.objects.none()
        # Role 2 sees their own department and below
        if profile.role == UserRole.ROLE_2:
            descendant_ids = _gather_descendant_ids(assigned_division)
            return Division.objects.filter(id__in=descendant_ids).prefetch_related("child_divisions")
        # Role 5 (HR admin) may or may not include child divisions and may be limited to a division type
        if profile.role == UserRole.ROLE_5:
            qs = None
            if getattr(profile, "include_child_divisions", False):
                descendant_ids = _gather_descendant_ids(assigned_division)
                qs = Division.objects.filter(id__in=descendant_ids)
            else:
                qs = Division.objects.filter(id=assigned_division.id)
            division_type_assignment = getattr(profile, "division_type_assignment", None)
            if division_type_assignment:
                qs = qs.filter(division_type=division_type_assignment)
            return qs.prefetch_related("child_divisions")
        # Roles 3 and 6 see only their assigned division
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
        # Ensure the user has rights to update this division
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
        update_dates = set()
        for item in item_serializer.validated_data:
            employee_id = item.get("employee_id")
            try:
                employee = Employee.objects.get(id=employee_id, division=division)
            except Employee.DoesNotExist:
                return Response(
                    {"error": f"Employee with id {employee_id} not found in this division."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            date_from = item.get("date_from")
            date_to = item.get("date_to") or date_from
            if date_to and date_to < date_from:
                return Response(
                    {"error": "date_to cannot be earlier than date_from."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            status_logs.append(
                EmployeeStatusLog(
                    employee=employee,
                    status=item.get("status"),
                    date_from=date_from,
                    date_to=date_to,
                    comment=item.get("comment", ""),
                    created_by=request.user,
                )
            )
            # Record all dates in the range for updating DivisionStatusUpdate
            current_day = date_from
            while current_day <= date_to:
                update_dates.add(current_day)
                current_day += datetime.timedelta(days=1)
        # Bulk create status logs
        EmployeeStatusLog.objects.bulk_create(status_logs)
        # Mark the division (and implicitly its hierarchy) as updated for each date
        for update_date in update_dates:
            DivisionStatusUpdate.objects.update_or_create(
                division=division,
                update_date=update_date,
                defaults={
                    "is_updated": True,
                    "updated_at": timezone.now(),
                    "updated_by": request.user,
                },
            )
        return Response({"status": "Statuses updated successfully."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):
        """
        Generate and return an expense report for this division in the
        specified format.  This action checks that statuses for the
        selected date have been updated across the division hierarchy
        before allowing report generation.  The generated report is also
        saved to ``PersonnelReport`` for future retrieval.
        """
        division = self.get_object()
        report_date = datetime.date.today()
        output_format = request.query_params.get("format", "docx")
        # Ensure all relevant divisions have updated statuses
        descendant_ids = _gather_descendant_ids(division)
        if DivisionStatusUpdate.objects.filter(
            division_id__in=descendant_ids, update_date=report_date, is_updated=False
        ).exists():
            return Response(
                {"error": "Cannot generate report until all divisions have updated their statuses."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        buffer = None
        content_type = ""
        filename = ""
        # For DOCX format produce a detailed report in accordance with the specification
        if output_format == "docx":
            buffer = generate_detailed_report_docx(division, report_date)
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"expense_report_{division.name}_{report_date}.docx"
        elif output_format == "xlsx":
            # XLSX reports remain summary style for now
            stats = get_division_statistics(division, report_date)
            buffer = generate_expense_report_xlsx(stats)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"expense_report_{division.name}_{report_date}.xlsx"
        elif output_format == "pdf":
            stats = get_division_statistics(division, report_date)
            buffer = generate_expense_report_pdf(stats)
            content_type = "application/pdf"
            filename = f"expense_report_{division.name}_{report_date}.pdf"
        else:
            return Response(
                {"error": "Invalid format specified. Use 'docx', 'xlsx', or 'pdf'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Persist the report
        report = PersonnelReport.objects.create(
            division=division,
            report_date=report_date,
            report_type="DAILY",
            date_from=report_date,
            date_to=None,
            created_by=request.user,
        )
        # Use ContentFile to attach the buffer to the FileField.  The
        # buffer may be a BytesIO or similar; call getvalue() if needed.
        content = buffer.getvalue() if hasattr(buffer, "getvalue") else buffer.read()
        report.file.save(filename, ContentFile(content))
        report.save()
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["get"], url_path="periodic-report")
    def periodic_report(self, request, pk=None):
        """
        Generate and return an expense report for a date range in the
        specified format.  Similar to ``report`` but accepts
        ``date_from`` and ``date_to`` query parameters.  Only allowed if
        all divisions have updated statuses for every date in the range.
        The report is saved to ``PersonnelReport`` as a ``PERIOD`` type.
        """
        division = self.get_object()
        date_from_str = request.query_params.get("date_from")
        date_to_str = request.query_params.get("date_to")
        output_format = request.query_params.get("format", "docx")
        if not date_from_str or not date_to_str:
            return Response(
                {"error": "Please provide 'date_from' and 'date_to' query parameters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            date_from = datetime.date.fromisoformat(date_from_str)
            date_to = datetime.date.fromisoformat(date_to_str)
        except ValueError:
            return Response(
                {"error": "Invalid date format. Please use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if date_to < date_from:
            return Response(
                {"error": "date_to cannot be earlier than date_from."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Ensure all dates in the range are updated
        descendant_ids = _gather_descendant_ids(division)
        current_day = date_from
        while current_day <= date_to:
            if DivisionStatusUpdate.objects.filter(
                division_id__in=descendant_ids, update_date=current_day, is_updated=False
            ).exists():
                return Response(
                    {"error": f"Cannot generate report until all divisions have updated their statuses for {current_day}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            current_day += datetime.timedelta(days=1)
        buffer = None
        content_type = ""
        filename = ""
        if output_format == "docx":
            buffer = generate_detailed_periodic_report_docx(division, date_from, date_to)
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"periodic_report_{division.name}_{date_from_str}_to_{date_to_str}.docx"
        elif output_format == "xlsx":
            buffer = generate_periodic_report_xlsx(division, date_from, date_to)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"periodic_report_{division.name}_{date_from_str}_to_{date_to_str}.xlsx"
        elif output_format == "pdf":
            buffer = generate_periodic_report_pdf(division, date_from, date_to)
            content_type = "application/pdf"
            filename = f"periodic_report_{division.name}_{date_from_str}_to_{date_to_str}.pdf"
        else:
            return Response(
                {"error": "Invalid format specified. Use 'docx', 'xlsx', or 'pdf'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Persist the report
        report = PersonnelReport.objects.create(
            division=division,
            report_date=datetime.date.today(),
            report_type="PERIOD",
            date_from=date_from,
            date_to=date_to,
            created_by=request.user,
        )
        content = buffer.getvalue() if hasattr(buffer, "getvalue") else buffer.read()
        report.file.save(filename, ContentFile(content))
        report.save()
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
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
    @method_decorator(cache_page(settings.CACHE_TIMEOUT))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    permission_classes = [IsRole4 | IsRole5 | (IsReadOnly & (IsRole1 | IsRole2 | IsRole3 | IsRole6))]
    @method_decorator(cache_page(settings.CACHE_TIMEOUT))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, "profile"):
            return Employee.objects.none()
        base_queryset = Employee.objects.select_related("position", "division").order_by(
            "position__level", "full_name"
        )
        profile = user.profile
        # Role 1 and 4 see all employees
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return base_queryset.all()
        assigned_division = profile.division_assignment
        if not assigned_division:
            return Employee.objects.none()
        # Role 2 and Role 5 (with include_child_divisions) see their division and below
        if profile.role == UserRole.ROLE_2 or (
            profile.role == UserRole.ROLE_5 and getattr(profile, "include_child_divisions", False)
        ):
            descendant_ids = _gather_descendant_ids(assigned_division)
            qs = base_queryset.filter(division__id__in=descendant_ids)
        elif profile.role in [UserRole.ROLE_3, UserRole.ROLE_6]:
            qs = base_queryset.filter(division__id=assigned_division.id)
        elif profile.role == UserRole.ROLE_5:
            # Role 5 without child divisions sees only their assigned division
            qs = base_queryset.filter(division__id=assigned_division.id)
        else:
            qs = Employee.objects.none()
        # Enforce division type assignment for Role 5
        if profile.role == UserRole.ROLE_5:
            division_type_assignment = getattr(profile, "division_type_assignment", None)
            if division_type_assignment:
                qs = qs.filter(division__division_type=division_type_assignment)
        # Order seconded employees to the bottom for clarity
        qs = qs.annotate(
            is_seconded_out=models.Exists(
                EmployeeStatusLog.objects.filter(
                    employee=models.OuterRef("pk"),
                    status=EmployeeStatusType.SECONDED_OUT,
                    date_to__isnull=True,
                )
            )
        ).order_by("is_seconded_out", "position__level", "full_name")
        return qs
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
            # Check both source and destination divisions
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
        "employee__position",
        "from_division",
        "to_division",
        "requested_by",
        "approved_by",
    )
    serializer_class = SecondmentRequestSerializer
    permission_classes = [IsRole4 | IsRole5]
    def perform_create(self, serializer):
        serializer.save()
    @action(detail=True, methods=["post"], permission_classes=[IsRole4 | IsRole5])
    def approve(self, request, pk=None):
        instance = self.get_object()
        if instance.status != SecondmentStatus.PENDING:
            return Response({"error": "Only pending requests can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        instance.status = SecondmentStatus.APPROVED
        instance.approved_by = request.user
        instance.save()
        # Create status logs for the secondment.  Mark the employee as
        # seconded out of their home division and as seconded in to the
        # receiving division.  Both logs share the same period.
        EmployeeStatusLog.objects.create(
            employee=instance.employee,
            status=EmployeeStatusType.SECONDED_OUT,
            date_from=instance.date_from,
            date_to=instance.date_to,
            comment=f"Seconded to {instance.to_division.name}",
            secondment_division=instance.to_division,
            created_by=request.user,
        )
        EmployeeStatusLog.objects.create(
            employee=instance.employee,
            status=EmployeeStatusType.SECONDED_IN,
            date_from=instance.date_from,
            date_to=instance.date_to,
            comment=f"From {instance.from_division.name}",
            secondment_division=instance.to_division,
            created_by=request.user,
        )
        return Response(self.get_serializer(instance).data)
    @action(detail=True, methods=["post"], permission_classes=[IsRole4 | IsRole5])
    def return_from_secondment(self, request, pk=None):
        """
        End a secondment early or on its planned end date and return the
        employee to their original division.  This action closes the
        existing status log and creates a new log returning the employee
        to ``ON_DUTY_SCHEDULED``.  Only approved secondments can be returned.
        """
        instance = self.get_object()
        if instance.status != SecondmentStatus.APPROVED:
            return Response(
                {"error": "Only approved secondments can be returned."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Only the receiving division's HR or admin can approve a return
        profile = getattr(request.user, "profile", None)
        if profile and profile.role == UserRole.ROLE_5 and profile.division_assignment != instance.to_division:
            return Response(
                {"error": "Only the receiving division's HR administrator can approve the return."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Close the secondment status logs
        today = datetime.date.today()
        status_log = EmployeeStatusLog.objects.filter(
            employee=instance.employee,
            status=EmployeeStatusType.SECONDED_OUT,
            date_from=instance.date_from,
            date_to=instance.date_to,
        ).first()
        if status_log:
            status_log.date_to = today
            status_log.save(update_fields=["date_to"])
        # Create a new log returning to duty
        EmployeeStatusLog.objects.create(
            employee=instance.employee,
            status=EmployeeStatusType.ON_DUTY_SCHEDULED,
            date_from=today,
            date_to=None,
            comment=f"Returned from secondment at {instance.to_division.name}",
            created_by=request.user,
        )
        instance.status = SecondmentStatus.CANCELLED
        instance.save(update_fields=["status"])
        return Response(self.get_serializer(instance).data)


class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.all().select_related(
        "staffing_unit__division",
        "staffing_unit__position",
        "created_by",
        "closed_by",
    )
    serializer_class = VacancySerializer
    permission_classes = [IsRole4 | IsRole5]
    @action(detail=True, methods=["post"], permission_classes=[IsRole4 | IsRole5])
    def close(self, request, pk=None):
        vacancy = self.get_object()
        if not vacancy.is_active:
            return Response({"error": "This vacancy is already closed."}, status=status.HTTP_400_BAD_REQUEST)
        vacancy.is_active = False
        vacancy.closed_at = timezone.now()
        vacancy.closed_by = request.user
        vacancy.save(update_fields=["is_active", "closed_at", "closed_by"])
        return Response(self.get_serializer(vacancy).data)


class StaffingUnitViewSet(viewsets.ModelViewSet):
    queryset = StaffingUnit.objects.all().select_related("division", "position")
    serializer_class = StaffingUnitSerializer
    permission_classes = [IsRole4 | IsRole5]
    @method_decorator(cache_page(settings.CACHE_TIMEOUT))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
