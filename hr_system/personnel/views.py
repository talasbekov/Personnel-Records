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
from .permissions import IsRole4, IsRole5, IsRole3, IsRole6


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