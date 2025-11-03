from typing import Dict, Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.models import Employee
from organization_management.apps.statuses.models import EmployeeStatus
from organization_management.apps.staff_unit.models import StaffUnit


class DataAggregator:
    """
    Сборщик данных для отчетов по расходу на дату.

    Рассчитывает по каждому подразделению:
    - Штатная численность (count StaffUnit)
    - В строю, Отпуск, Больничный, Командировка, Учёба, Прочие отсутствия
    - Прикомандировано (входящие) и Откомандировано (исходящие)
    - Итого наличествует = В строю + Прикомандировано
    - Процент наличия = Итого / Штатная * 100
    """

    def _division_subtree_ids(self, division: Division):
        return division.get_descendants(include_self=True).values_list("id", flat=True)

    def _reference_date(self, report):
        if report.date_to:
            return report.date_to
        if report.date_from:
            return report.date_from
        return timezone.now().date()

    def collect_data(self, report) -> Dict[str, Any]:
        # Область охвата
        if report.division_id:
            division_ids = list(self._division_subtree_ids(report.division))
        else:
            division_ids = list(Division.objects.values_list("id", flat=True))

        ref_date = self._reference_date(report)

        # Сотрудники (только работающие)
        employees = Employee.objects.filter(
            division_id__in=division_ids,
            employment_status=Employee.EmploymentStatus.WORKING,
        )

        # Текущие статусы на дату: отбираем все записи, перекрывающие дату
        statuses = EmployeeStatus.objects.filter(
            employee_id__in=employees.values_list("id", flat=True),
            start_date__lte=ref_date,
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=ref_date))

        # Карты: по type и домашнему подразделению сотрудника
        def _map_by_division(status_type: str) -> Dict[int, int]:
            qs = statuses.filter(status_type=status_type).values("employee__division_id").annotate(total=Count("id"))
            return {row["employee__division_id"]: row["total"] for row in qs}

        in_service_map = _map_by_division(EmployeeStatus.StatusType.IN_SERVICE)
        vacation_map = _map_by_division(EmployeeStatus.StatusType.VACATION)
        sick_map = _map_by_division(EmployeeStatus.StatusType.SICK_LEAVE)
        bt_map = _map_by_division(EmployeeStatus.StatusType.BUSINESS_TRIP)
        training_map = _map_by_division(EmployeeStatus.StatusType.TRAINING)
        other_map = _map_by_division(EmployeeStatus.StatusType.OTHER_ABSENCE)
        seconded_out_map = _map_by_division(EmployeeStatus.StatusType.SECONDED_TO)

        # Прикомандированные считаем по related_division (входящие на приемную сторону)
        incoming_qs = statuses.filter(status_type=EmployeeStatus.StatusType.SECONDED_TO).values("related_division_id").annotate(total=Count("id"))
        seconded_in_map = {row["related_division_id"]: row["total"] for row in incoming_qs}

        # Общее число сотрудников по подразделению
        total_working_map = {
            row["division_id"]: row["total"]
            for row in employees.values("division_id").annotate(total=Count("id"))
        }

        # Штатная численность (количество штатных единиц по подразделению)
        staffing_map = {
            row["division_id"]: row["qty"]
            for row in StaffUnit.objects.filter(division_id__in=division_ids)
            .values("division_id")
            .annotate(qty=Count("id"))
        }

        rows = []
        for d in Division.objects.filter(id__in=division_ids).values("id", "name"):
            did = d["id"]
            total = total_working_map.get(did, 0)

            # Сумма известных статусов (кроме incoming, т.к. они считаются на приемнике отдельно)
            known = (
                in_service_map.get(did, 0)
                + vacation_map.get(did, 0)
                + sick_map.get(did, 0)
                + bt_map.get(did, 0)
                + training_map.get(did, 0)
                + other_map.get(did, 0)
                + seconded_out_map.get(did, 0)
            )

            # Сотрудники без статуса на дату считаются "В строю"
            inferred_in_service = max(0, total - known)
            in_service = in_service_map.get(did, 0) + inferred_in_service

            seconded_in = seconded_in_map.get(did, 0)
            seconded_out = seconded_out_map.get(did, 0)

            present_total = in_service + seconded_in
            staffing_qty = staffing_map.get(did, 0) or 0
            presence_pct = (present_total / staffing_qty * 100.0) if staffing_qty else 0.0

            rows.append(
                {
                    "division_id": did,
                    "division_name": d["name"],
                    "staff_unit": staffing_qty,
                    "in_service": in_service,
                    "vacation": vacation_map.get(did, 0),
                    "sick_leave": sick_map.get(did, 0),
                    "business_trip": bt_map.get(did, 0),
                    "training": training_map.get(did, 0),
                    "seconded_in": seconded_in,
                    "seconded_out": seconded_out,
                    "other_absence": other_map.get(did, 0),
                    "present_total": present_total,
                    "presence_pct": round(presence_pct, 2),
                }
            )

        return {
            "division": report.division.name if report.division_id else "Вся организация",
            "date": str(ref_date),
            "rows": rows,
        }
