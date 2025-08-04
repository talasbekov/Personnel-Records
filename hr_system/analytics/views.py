"""
Viewsets for the analytics API.

The endpoints defined here provide high‑level statistics about the
organisation such as status distributions, division staffing and
key performance indicators.  These endpoints are read‑only and
accessible to any authenticated user who has at least read access
within the personnel module.  Data is aggregated on the fly from
existing models in the ``personnel`` app.

TODO: In the future, more advanced dashboards and graphs could be
implemented using charting libraries or by exporting data to BI tools.
"""

import datetime
from collections import defaultdict

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from django.db.models import Count, Q, F
from django.utils import timezone

from personnel.models import (
    Division,
    Employee,
    EmployeeStatusLog,
    EmployeeStatusType,
    Vacancy,
    StaffingUnit,
    DivisionStatusUpdate,
    UserRole,
)


class AnalyticsViewSet(viewsets.ViewSet):
    """
    A lightweight viewset that exposes analytics across the personnel
    system.  All methods are read‑only and will never modify data.

    Permissions are intentionally permissive: any authenticated user
    with at least read access (Role 1) can request analytics.  The
    underlying queries still respect division assignments where
    applicable by reusing the queryset logic from the personnel
    viewsets.
    """

    def _filter_by_division_scope(self, request, base_queryset):
        """
        Restrict a queryset to the divisions visible to the requesting user.

        This helper replicates the division scoping logic from
        ``DivisionViewSet.get_queryset``.  It returns a filtered
        queryset of Division IDs that the user can see.  For users with
        unlimited access (Role 1 or Role 4) the original queryset is
        returned.  For others, the set of allowed division IDs is
        applied as a filter on ``base_queryset``.
        """
        user = request.user
        if not user.is_authenticated or not hasattr(user, "profile"):
            return base_queryset.none()
        profile = user.profile
        if profile.role in [UserRole.ROLE_1, UserRole.ROLE_4]:
            return base_queryset
        assigned_division = profile.division_assignment
        if not assigned_division:
            return base_queryset.none()
        # gather descendant IDs if children included or role 2
        from personnel.views import _gather_descendant_ids
        if profile.role == UserRole.ROLE_2 or (
            profile.role == UserRole.ROLE_5 and getattr(profile, "include_child_divisions", False)
        ):
            descendant_ids = _gather_descendant_ids(assigned_division)
            qs = base_queryset.filter(division__id__in=descendant_ids)
        else:
            qs = base_queryset.filter(division__id=assigned_division.id)
        if profile.role == UserRole.ROLE_5:
            division_type_assignment = getattr(profile, "division_type_assignment", None)
            if division_type_assignment:
                qs = qs.filter(division__division_type=division_type_assignment)
        return qs

    @action(detail=False, methods=["get"])
    def division_statistics(self, request):
        """
        Return statistics for each division within the user's scope.

        The response structure is a list of divisions with counts of
        employees by their current status (on duty, leave, sick, seconded
        etc.) and counts of staffing units and vacancies.  The date for
        determining current status may be specified via the ``date`` query
        parameter (default: today).  This endpoint is intended to drive
        summary dashboards.
        """
        date_str = request.query_params.get("date")
        try:
            reference_date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response({"error": "Invalid date parameter."}, status=status.HTTP_400_BAD_REQUEST)
        # Build a map of employee status on the given date
        status_map = defaultdict(lambda: defaultdict(int))
        # Preload statuses for employees in scope to avoid N+1 queries
        employees = self._filter_by_division_scope(request, Employee.objects.select_related("division"))
        # Query logs that cover the date
        logs = EmployeeStatusLog.objects.filter(
            employee__in=employees,
            date_from__lte=reference_date,
        ).filter(Q(date_to__gte=reference_date) | Q(date_to__isnull=True)).select_related("employee__division")
        for log in logs:
            status_map[log.employee.division_id][log.status] += 1
        # Count staffing units and vacancies per division
        staffing_counts = (
            StaffingUnit.objects.filter(division__in=self._filter_by_division_scope(request, Division.objects.all()))
            .values("division_id")
            .annotate(total_units=Count("id"))
        )
        staffing_dict = {item["division_id"]: item["total_units"] for item in staffing_counts}
        vacancy_counts = (
            Vacancy.objects.filter(is_active=True, staffing_unit__division__in=self._filter_by_division_scope(request, Division.objects.all()))
            .values("staffing_unit__division_id")
            .annotate(open_vacancies=Count("id"))
        )
        vacancy_dict = {item["staffing_unit__division_id"]: item["open_vacancies"] for item in vacancy_counts}
        # Build response list
        divisions = self._filter_by_division_scope(request, Division.objects.all())
        result = []
        for div in divisions:
            stats = {
                "division_id": div.id,
                "division_name": div.name,
                "on_duty": status_map[div.id].get(EmployeeStatusType.ON_DUTY_SCHEDULED, 0)
                + status_map[div.id].get(EmployeeStatusType.ON_DUTY_ACTUAL, 0),
                "leave": status_map[div.id].get(EmployeeStatusType.ON_LEAVE, 0),
                "sick_leave": status_map[div.id].get(EmployeeStatusType.SICK_LEAVE, 0),
                "training": status_map[div.id].get(EmployeeStatusType.TRAINING_ETC, 0),
                "business_trip": status_map[div.id].get(EmployeeStatusType.BUSINESS_TRIP, 0),
                "seconded_out": status_map[div.id].get(EmployeeStatusType.SECONDED_OUT, 0),
                "seconded_in": status_map[div.id].get(EmployeeStatusType.SECONDED_IN, 0),
                "staffing_units": staffing_dict.get(div.id, 0),
                "open_vacancies": vacancy_dict.get(div.id, 0),
            }
            result.append(stats)
        return Response(result)

    @action(detail=False, methods=["get"])
    def kpi(self, request):
        """
        Return high‑level key performance indicators for the organisation.

        KPIs include the total number of active employees, the number of
        employees currently on duty, the number of open vacancies, and
        the percentage of divisions that have updated their statuses for
        today.  Users see KPIs relative to their permitted division
        scope.
        """
        today = timezone.now().date()
        employees = self._filter_by_division_scope(request, Employee.objects.filter(is_active=True))
        total_active = employees.count()
        # Determine employees on duty (scheduled or actual) today
        on_duty = EmployeeStatusLog.objects.filter(
            employee__in=employees,
            status__in=[EmployeeStatusType.ON_DUTY_SCHEDULED, EmployeeStatusType.ON_DUTY_ACTUAL],
            date_from__lte=today,
        ).filter(Q(date_to__gte=today) | Q(date_to__isnull=True)).count()
        # Count open vacancies within scope
        open_vacancies = Vacancy.objects.filter(is_active=True, staffing_unit__division__in=self._filter_by_division_scope(request, Division.objects.all())).count()
        # Percentage of divisions updated today
        divisions = self._filter_by_division_scope(request, Division.objects.all())
        total_divs = divisions.count()
        updated_divs = DivisionStatusUpdate.objects.filter(
            division__in=divisions,
            update_date=today,
            is_updated=True,
        ).values("division").distinct().count()
        status_update_rate = (updated_divs / total_divs) * 100 if total_divs > 0 else 0.0
        return Response(
            {
                "total_active_employees": total_active,
                "employees_on_duty": on_duty,
                "open_vacancies": open_vacancies,
                "divisions_status_update_rate": round(status_update_rate, 2),
            }
        )
