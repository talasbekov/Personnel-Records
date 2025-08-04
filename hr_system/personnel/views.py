"""
Viewsets and API endpoints for managing organisational structure and
related operations.

This module introduces a ``DivisionViewSet`` that provides CRUD
functionality for organisational divisions as well as custom actions
for creating new departments, moving divisions within the hierarchy,
and performing bulk import/export of the structure.  The logic here
enforces structural constraints to prevent cycles in the hierarchy and
delegates validation of business rules (such as division types and
hierarchy variants) to the serializer.

The endpoints are designed to align with the requirements of the
technical specification, enabling administrators and role‑based
operators to maintain the organisation chart via RESTful calls.
"""

from typing import Any, Dict, Iterable

import datetime
from django.utils import timezone

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

try:
    from .models import Division
except Exception:  # pragma: no cover
    Division = None  # type: ignore
from .serializers import DivisionSerializer
from .serializers import (
    PositionSerializer,
    EmployeeSerializer,
    UserProfileSerializer,
    SecondmentRequestSerializer,
    EmployeeStatusLogSerializer,
    StaffingUnitSerializer,
    VacancySerializer,
)
from .permissions import IsRole4, IsRole5, IsRole3, IsRole6
from .throttles import ReportGenerationThrottle


class DivisionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing divisions in the organisational hierarchy.

    By default this viewset exposes list, retrieve, create, update and
    delete actions.  Additional actions are provided for bulk import,
    export, creation of departments and relocating divisions.
    """

    queryset = Division.objects.all() if Division else []  # type: ignore[assignment]
    serializer_class = DivisionSerializer

    def get_permissions(self):  # type: ignore[override]
        """Return the list of permissions that this view requires.

        Administrators (role 4) and HR administrators (role 5) may
        perform all operations.  Division heads (role 3 and role 6)
        have limited access and must be restricted by the serializer
        and object checks.  The viewset itself does not perform
        secondment or scope checks; these are enforced via the
        permissions and serializer validators.
        """
        permission_classes = [IsRole4 | IsRole5 | IsRole3 | IsRole6]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["post"], url_path="create-division")
    def create_division(self, request, *args, **kwargs):
        """Create a new division within the organisational hierarchy.

        Expects JSON data representing the division fields.  A
        ``parent_division`` may be supplied to nest the new division
        under an existing one.  Validation of division types and
        hierarchy variants is delegated to the serializer.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], url_path="move")
    def move_division(self, request, pk=None):
        """Move the specified division under a new parent division.

        This action requires a JSON body with a ``parent_id`` field
        indicating the ID of the new parent.  The method checks for
        cycles (i.e. ensuring the new parent is not a descendant of
        the division being moved) and updates the ``parent_division``
        accordingly.  If ``parent_id`` is null or omitted, the
        division is moved to the root level.
        """
        if Division is None:
            return Response({"detail": "Division model unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        division = self.get_object()
        parent_id = request.data.get("parent_id")
        new_parent = None
        if parent_id:
            try:
                new_parent = Division.objects.get(pk=parent_id)
            except Division.DoesNotExist:
                return Response({"detail": "Parent division not found"}, status=status.HTTP_404_NOT_FOUND)
            # Prevent moving under self or descendants
            current = new_parent
            while current:
                if current.pk == division.pk:
                    return Response(
                        {"detail": "Cannot move a division into its own subtree"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                current = current.parent_division
        division.parent_division = new_parent
        division.save()
        return Response(self.get_serializer(division).data)

    @action(detail=False, methods=["post"], url_path="bulk-import")
    def bulk_import_structure(self, request):
        """Bulk import organisational structure from an uploaded file.

        Accepts a multipart/form‑data request with a file in a format
        such as CSV or Excel.  The file is parsed and divisions are
        created or updated accordingly.  This is a placeholder
        implementation; actual parsing logic should be added to
        accommodate the chosen format and field mapping.
        """
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "File is required"}, status=status.HTTP_400_BAD_REQUEST)
        # TODO: Parse and import the structure.  Example of how a CSV might be handled:
        # import csv
        # reader = csv.DictReader(uploaded.read().decode().splitlines())
        # for row in reader:
        #     ...
        return Response({"detail": "Import not yet implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)

    @action(detail=False, methods=["get"], url_path="export")
    def export_structure(self, request):
        """Export the organisational structure to a file.

        Generates a simple CSV representation of the divisions and
        returns it as a downloadable response.  Extend this method to
        support additional formats such as Excel or JSON based on
        requirements.
        """
        if Division is None:
            return Response({"detail": "Division model unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        # Build CSV content
        lines: Iterable[str] = ["id,name,division_type,parent_id,hierarchy_variant"]
        for div in Division.objects.all():
            parent_id = div.parent_division_id if getattr(div, "parent_division_id", None) else ""
            lines.append(f"{div.pk},{div.name},{div.division_type},{parent_id},{div.hierarchy_variant}")
        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=divisions.csv"
        return response

    @action(detail=True, methods=["get"], url_path="report", throttle_classes=[ReportGenerationThrottle])
    def report(self, request, pk=None):
        """Generate a daily or ranged personnel lineup report (.docx).

        Query parameters:
        - ``date``: single date in YYYY-MM-DD format (defaults to today)
        - ``date_from`` and ``date_to``: start and end dates for a range

        Returns a Word document constructed by
        ``generate_detailed_report_docx``.  The filename encodes the
        division name and date(s).
        """
        if Division is None:
            return Response({"detail": "Division model unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            from .services import generate_detailed_report_docx
        except Exception:
            return Response({"detail": "Report service unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        division = self.get_object()
        # Parse dates
        date_str = request.query_params.get("date")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        try:
            if date_from:
                start = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
            elif date_str:
                start = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                start = timezone.now().date()
            if date_to:
                end = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
            else:
                end = start
        except ValueError:
            return Response({"detail": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)
        # Generate document
        doc_buffer = generate_detailed_report_docx(division, start, end)
        # Build response
        filename = f"report_{division.pk}_{start.strftime('%Y%m%d')}.docx" if start == end else f"report_{division.pk}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.docx"
        response = HttpResponse(doc_buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        response["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    @action(detail=False, methods=["get"], url_path="status-summary")
    def status_summary(self, request):
        """Return status indicators for all divisions for today.

        The result maps division IDs to a simple status indicator:
        - GREEN: all status updates completed
        - YELLOW: partially updated
        - RED: not updated
        The logic relies on the ``DivisionStatusUpdate`` model to
        determine completeness.
        """
        try:
            from .models import DivisionStatusUpdate
        except Exception:
            return Response({"detail": "Status update model unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        today = timezone.now().date()
        result: Dict[str, str] = {}
        # Collect status updates grouped by division
        updates = DivisionStatusUpdate.objects.filter(update_date=today)
        by_division: Dict[int, list[bool]] = {}
        for upd in updates:
            by_division.setdefault(upd.division_id, []).append(upd.is_updated)
        for division_id, flags in by_division.items():
            if all(flags):
                indicator = "GREEN"
            elif any(flags):
                indicator = "YELLOW"
            else:
                indicator = "RED"
            result[str(division_id)] = indicator
        return Response(result)


class PositionViewSet(viewsets.ModelViewSet):
    """CRUD viewset for positions."""

    try:
        from .models import Position  # type: ignore
        queryset = Position.objects.all()
    except Exception:
        queryset = []  # type: ignore
    serializer_class = PositionSerializer
    permission_classes = [IsRole4 | IsRole5]


class EmployeeViewSet(viewsets.ModelViewSet):
    """CRUD viewset for employees with support for bulk status updates."""

    try:
        from .models import Employee  # type: ignore
        queryset = Employee.objects.all()
    except Exception:
        queryset = []  # type: ignore
    serializer_class = EmployeeSerializer
    permission_classes = [IsRole4 | IsRole5 | IsRole3 | IsRole6]

    @action(detail=False, methods=["post"], url_path="bulk-update-statuses")
    def bulk_update_statuses(self, request):
        """Mass update statuses for multiple employees.

        Expects a list of objects with keys: employee_id, status, date_from,
        date_to (optional), and comment (optional).  Creates new
        EmployeeStatusLog entries for each provided record.  This is a
        minimal implementation; proper validation and conflict
        detection should be added according to business rules.
        """
        updates = request.data if isinstance(request.data, list) else request.data.get("updates", [])
        if not updates:
            return Response({"detail": "No updates provided"}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        try:
            from .models import EmployeeStatusLog, EmployeeStatusType, Employee
        except Exception:
            return Response({"detail": "Models unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        for item in updates:
            emp_id = item.get("employee_id")
            status_code = item.get("status")
            date_from = item.get("date_from")
            date_to = item.get("date_to")
            comment = item.get("comment")
            if not emp_id or not status_code or not date_from:
                continue
            try:
                emp = Employee.objects.get(pk=emp_id)
            except Employee.DoesNotExist:
                continue
            EmployeeStatusLog.objects.create(
                employee=emp,
                status=status_code,
                date_from=date_from,
                date_to=date_to,
                comment=comment,
                created_by=request.user,
            )
            created.append(emp_id)
        return Response({"updated": created})


class UserProfileViewSet(viewsets.ModelViewSet):
    """CRUD viewset for user profiles."""

    try:
        from .models import UserProfile  # type: ignore
        queryset = UserProfile.objects.all()
    except Exception:
        queryset = []  # type: ignore
    serializer_class = UserProfileSerializer
    permission_classes = [IsRole4]


class SecondmentRequestViewSet(viewsets.ModelViewSet):
    """Viewset for managing secondment requests."""

    try:
        from .models import SecondmentRequest  # type: ignore
        queryset = SecondmentRequest.objects.all()
    except Exception:
        queryset = []  # type: ignore
    serializer_class = SecondmentRequestSerializer
    permission_classes = [IsRole4 | IsRole5 | IsRole3]

    @action(detail=True, methods=["post"], url_path="approve")
    def approve_secondment(self, request, pk=None):
        """Approve a secondment request and create status logs."""
        try:
            from .models import EmployeeStatusLog, EmployeeStatusType
        except Exception:
            return Response({"detail": "Models unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        req = self.get_object()
        # Update request status
        req.status = "approved"  # placeholder value
        req.save()
        # Create status logs for the employee in both divisions
        EmployeeStatusLog.objects.create(
            employee=req.employee,
            status=EmployeeStatusType.SECONDED_OUT,
            date_from=req.date_from,
            date_to=req.date_to,
            secondment_division=req.to_division,
            comment="Seconded",
            created_by=request.user,
        )
        return Response(self.get_serializer(req).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject_secondment(self, request, pk=None):
        """Reject a secondment request."""
        req = self.get_object()
        req.status = "rejected"
        req.save()
        return Response(self.get_serializer(req).data)

    @action(detail=True, methods=["post"], url_path="return-from-secondment")
    def return_from_secondment(self, request, pk=None):
        """Handle the return of an employee from secondment."""
        try:
            from .models import EmployeeStatusLog, EmployeeStatusType
        except Exception:
            return Response({"detail": "Models unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        req = self.get_object()
        # Update request status
        req.status = "returned"
        req.save()
        # Create log returning to duty
        EmployeeStatusLog.objects.create(
            employee=req.employee,
            status=EmployeeStatusType.ON_DUTY_SCHEDULED,
            date_from=req.date_to or req.date_from,
            date_to=None,
            comment="Returned from secondment",
            created_by=request.user,
        )
        return Response(self.get_serializer(req).data)


class EmployeeStatusLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read‑only viewset for employee status logs."""

    try:
        from .models import EmployeeStatusLog  # type: ignore
        queryset = EmployeeStatusLog.objects.all()
    except Exception:
        queryset = []  # type: ignore
    serializer_class = EmployeeStatusLogSerializer
    permission_classes = [IsRole4 | IsRole5 | IsRole3 | IsRole6]


class StaffingUnitViewSet(viewsets.ModelViewSet):
    """Viewset for staffing units."""
    try:
        from .models import StaffingUnit  # type: ignore
        queryset = StaffingUnit.objects.all()
    except Exception:
        queryset = []  # type: ignore
    serializer_class = StaffingUnitSerializer
    permission_classes = [IsRole4 | IsRole5]


class VacancyViewSet(viewsets.ModelViewSet):
    """Viewset for vacancies."""
    try:
        from .models import Vacancy  # type: ignore
        queryset = Vacancy.objects.all()
    except Exception:
        queryset = []  # type: ignore
    serializer_class = VacancySerializer
    permission_classes = [IsRole4 | IsRole5]