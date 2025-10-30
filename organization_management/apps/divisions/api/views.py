from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import DivisionSerializer
from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.models import Employee
from organization_management.apps.employees.api.serializers import EmployeeSerializer

from django.utils import timezone

class DivisionViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления подразделениями.
    Предоставляет CRUD операции и кастомные действия.
    """
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer

    def _get_department_root(self, division: Division) -> Division:
        """Возвращает ближайший ancestor уровня департамента или корень."""
        node = division
        # поднимаемся, пока не найдем департамент
        while node.parent and node.division_type != Division.DivisionType.DEPARTMENT:
            node = node.parent
        return node

    def get_queryset(self):
        user = self.request.user  # исправить
        qs = super().get_queryset()

        if not user.is_authenticated:
            return qs.none()

        if user.has_perm('organization_management.view_division'):
            return qs

        if not user.division_id:
            return qs.none()

        if user.has_perm('organization_management.view_division'):
            allowed = user.division.get_descendants(include_self=True)
        else:
            dept_root = self._get_department_root(user.division)
            allowed = dept_root.get_descendants(include_self=True)

        return qs.filter(id__in=allowed.values_list("id", flat=True))

    def get_permissions(self):
        """
        Определение прав доступа в зависимости от действия.
        """
        if self.action in ['create', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update']:
            self.permission_classes = [
                permissions.IsAuthenticated,
            ]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    @action(detail=True, methods=['get'])
    def employees(self, request, pk=None):
        """
        Получение списка сотрудников для конкретного подразделения.
        """
        division = self.get_object()
        employees = Employee.objects.filter(division=division)
        serializer = EmployeeSerializer(employees, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Мягкое удаление подразделения с проверками."""
        instance: Division = self.get_object()
        # запрет, если есть дочерние активные
        if instance.get_children().exists():
            return Response({'detail': 'Сначала удалите/переместите дочерние подразделения.'}, status=400)
        # запрет, если есть активные сотрудники
        from organization_management.apps.employees.models import Employee
        active_in_branch = Employee.objects.filter(
            division__in=instance.get_descendants(include_self=True),
            employment_status=Employee.EmploymentStatus.WORKING,
        ).exists()
        if active_in_branch:
            return Response({'detail': 'Нельзя удалить подразделение с активными сотрудниками.'}, status=400)

        instance.is_active = False
        instance.archived_at = timezone.now()
        instance.save(update_fields=['is_active', 'archived_at'])
        return Response(status=204)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def restore(self, request, pk=None):
        """Восстановление мягко удаленного подразделения."""
        instance: Division = self.get_object()
        instance.is_active = True
        instance.archived_at = None
        instance.save(update_fields=['is_active', 'archived_at'])
        return Response({'status': 'restored'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def move(self, request, pk=None):
        """
        Перемещение узла на нового родителя с валидациями:
        - нельзя переместить в самого себя или в собственного потомка
        - ограничение глубины до 5 уровней
        """
        instance: Division = self.get_object()
        parent_id = request.data.get('parent_id')
        if parent_id is None:
            instance.parent = None
            instance.save()
            return Response({'status': 'moved'})
        if int(parent_id) == instance.id:
            return Response({'detail': 'Нельзя переместить подразделение само в себя.'}, status=400)
        try:
            new_parent = Division.objects.get(pk=parent_id)
        except Division.DoesNotExist:
            return Response({'detail': 'Новый родитель не найден.'}, status=404)
        # запрет перемещения в потомка
        if new_parent in instance.get_descendants():
            return Response({'detail': 'Нельзя перемещать подразделение в собственный потомок.'}, status=400)

        # проверка глубины: глубина = глубина нового родителя + 1; ограничение <=5
        # вычислим будущую глубину как len(ancestors(new_parent)) + 1
        future_depth = len(new_parent.get_ancestors()) + 1
        if future_depth > 5:
            return Response({'detail': 'Превышена максимальная глубина вложенности (5).'}, status=400)

        instance.parent = new_parent
        instance.save()
        return Response({'status': 'moved'})
