from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import EmployeeSerializer
from organization_management.apps.employees.models import Employee
from organization_management.apps.divisions.models import Division
from organization_management.apps.staffing.models import Staffing
from organization_management.apps.employees.models import EmployeeTransferHistory
from django.db import transaction
from organization_management.apps.statuses.models import EmployeeStatus

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления сотрудниками.
    Предоставляет CRUD операции и кастомные действия.
    """
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    def _get_department_root(self, division: Division) -> Division:
        node = division
        while node.parent and node.division_type != Division.DivisionType.DEPARTMENT:
            node = node.parent
        return node

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if not user.is_authenticated:
            return qs.none()
        role = getattr(user, "role", None)
        if role in (user.RoleType.SYSTEM_ADMIN, user.RoleType.OBSERVER_ORG):  # type: ignore[attr-defined]
            return qs
        if not user.division_id:
            return qs.none()
        if role == user.RoleType.HR_ADMIN:  # type: ignore[attr-defined]
            allowed = user.division.get_descendants(include_self=True)
        else:
            dept_root = self._get_department_root(user.division)
            allowed = dept_root.get_descendants(include_self=True)
        return qs.filter(division_id__in=allowed.values_list("id", flat=True))

    def _gen_personnel_number(self) -> str:
        last = (
            Employee.objects.exclude(personnel_number="000000")
            .order_by('-id')
            .values_list('personnel_number', flat=True)
            .first()
        )
        try:
            num = int(last) + 1 if last and last.isdigit() else Employee.objects.count() + 1
        except ValueError:
            num = Employee.objects.count() + 1
        return str(num).zfill(6)

    def _inc_staffing(self, division_id, position_id):
        if not division_id or not position_id:
            return
        try:
            st = Staffing.objects.get(division_id=division_id, position_id=position_id)
            st.occupied = max(0, (st.occupied or 0)) + 1
            st.save(update_fields=['occupied'])
        except Staffing.DoesNotExist:
            return

    def _dec_staffing(self, division_id, position_id):
        if not division_id or not position_id:
            return
        try:
            st = Staffing.objects.get(division_id=division_id, position_id=position_id)
            st.occupied = max(0, (st.occupied or 0) - 1)
            st.save(update_fields=['occupied'])
        except Staffing.DoesNotExist:
            return

    def perform_create(self, serializer):
        data = serializer.validated_data
        if not data.get('personnel_number'):
            data['personnel_number'] = self._gen_personnel_number()
        if not data.get('employment_status'):
            data['employment_status'] = Employee.EmploymentStatus.WORKING
        instance = serializer.save()
        # увеличить занятость по штатке
        if instance.employment_status == Employee.EmploymentStatus.WORKING:
            self._inc_staffing(instance.division_id, instance.position_id)
            # Установить начальный статус "В строю" с даты приема
            try:
                EmployeeStatus.objects.create(
                    employee=instance,
                    status_type=EmployeeStatus.StatusType.IN_SERVICE,
                    start_date=instance.hire_date,
                    created_by=self.request.user,
                    comment="Начальный статус при приеме",
                )
            except Exception:
                pass
        return instance

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'destroy', 'dismiss']:
            # Прием/увольнение: Роль-4 и Роль-5
            self.permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['transfer']:
            # Перевод: Роль-4, Роль-5; а также Роль-3/6 в своей зоне (object-level)
            self.permission_classes = [
                permissions.IsAuthenticated
            ]
        elif self.action in ['update', 'partial_update']:
            # Редактирование: Роль-4/5 и Роль-3/6 в своей зоне
            self.permission_classes = [
                permissions.IsAuthenticated
            ]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        # Физическое удаление сотрудников запрещено согласно ТЗ (используйте увольнение)
        return Response({'detail': 'Удаление сотрудника запрещено. Используйте увольнение.'}, status=405)

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """
        Перевод сотрудника в другое подразделение.
        """
        employee = self.get_object()
        division_id = request.data.get('division_id')
        position_id = request.data.get('position_id')
        reason = request.data.get('reason', '')
        is_temporary = bool(request.data.get('is_temporary', False))
        end_date = request.data.get('end_date')

        if not division_id and not position_id:
            return Response({'detail': 'division_id or position_id required'}, status=400)

        with transaction.atomic():
            old_div, old_pos = employee.division_id, employee.position_id
            # create history
            EmployeeTransferHistory.objects.create(
                employee=employee,
                from_division_id=old_div,
                to_division_id=division_id or old_div,
                from_position_id=old_pos,
                to_position_id=position_id or old_pos,
                reason=reason,
                is_temporary=is_temporary,
                end_date=end_date,
            )
            # staffing counters
            if division_id and position_id and (old_div != division_id or old_pos != position_id):
                self._dec_staffing(old_div, old_pos)
                self._inc_staffing(division_id, position_id)

            # Ограничения для Роль-3/6: внутри своей зоны
            role = getattr(request.user, 'role', None)
            if role == request.user.RoleType.DIRECTORATE_HEAD and division_id:
                # Только внутри своего управления
                allowed = request.user.division.get_descendants(include_self=True)
                if int(division_id) not in allowed.values_list('id', flat=True):
                    return Response({'detail': 'Перевод вне вашего управления запрещен.'}, status=403)
            if role == request.user.RoleType.DIVISION_HEAD and division_id:
                # Только внутри своего отдела (фактически нельзя менять division)
                if int(division_id) != request.user.division_id:
                    return Response({'detail': 'Перевод вне вашего отдела запрещен.'}, status=403)

            if division_id:
                employee.division_id = division_id
            if position_id:
                employee.position_id = position_id
            employee.save(update_fields=['division', 'position'])

        return Response({'status': 'сотрудник переведен'})

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """
        Увольнение сотрудника.
        """
        employee = self.get_object()
        if employee.employment_status == Employee.EmploymentStatus.WORKING:
            self._dec_staffing(employee.division_id, employee.position_id)
        employee.employment_status = Employee.EmploymentStatus.FIRED
        employee.dismissal_date = request.data.get('dismissal_date')
        employee.save(update_fields=['employment_status', 'dismissal_date'])
        return Response({'status': 'сотрудник уволен'})

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Получение истории переводов сотрудника.
        """
        # ... (логика получения истории)
        return Response({'history': []})
