from rest_framework import serializers

from organization_management.apps.divisions.models import Division
from organization_management.apps.employees.models import Employee
from organization_management.apps.staff_unit.models import Vacancy, StaffUnit
from organization_management.apps.dictionaries.models import Position
from organization_management.apps.dictionaries.api.serializers import PositionSerializer as DictionaryPositionSerializer
from organization_management.apps.statuses.models import EmployeeStatus


class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = '__all__'

class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = ["id", "name"]


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "name"]

class EmployeeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeStatus
        fields = ("status_type", "state", "start_date", "end_date")


class EmployeeSerializer(serializers.ModelSerializer):
    current_status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "first_name", "last_name", "current_status"]

    def get_current_status(self, obj):
        status = (
            obj.statuses
            .filter(state=EmployeeStatus.StatusState.ACTIVE)
            .order_by("-start_date")
            .first()
        )
        return EmployeeStatusSerializer(status).data if status else {
            "status_type": EmployeeStatus.StatusType.IN_SERVICE,
            "state": EmployeeStatus.StatusState.ACTIVE,
        }


class StaffUnitSerializer(serializers.ModelSerializer):
    # Вложенные объекты для чтения
    division_data = DivisionSerializer(source='division', read_only=True)
    position_data = DictionaryPositionSerializer(source='position', read_only=True)
    employee_data = EmployeeSerializer(source='employee', read_only=True)
    vacancy_data = VacancySerializer(source='vacancy', read_only=True)

    # ID поля для записи
    division = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.all(),
        required=True,
        write_only=False
    )
    position = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(),
        required=True,
        write_only=False
    )
    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        required=False,
        allow_null=True,
        write_only=False
    )
    vacancy = serializers.PrimaryKeyRelatedField(
        queryset=Vacancy.objects.all(),
        required=False,
        allow_null=True,
        write_only=False
    )

    class Meta:
        model = StaffUnit
        fields = [
            "id",
            "division", "division_data",
            "position", "position_data",
            "employee", "employee_data",
            "vacancy", "vacancy_data",
            "index", "parent_id"
        ]

    def to_representation(self, instance):
        """Кастомизация вывода - показываем полные объекты, а не ID"""
        representation = super().to_representation(instance)
        # Заменяем ID на полные объекты для удобства фронтенда
        representation['division'] = representation.pop('division_data')
        representation['position'] = representation.pop('position_data')
        representation['employee'] = representation.pop('employee_data')
        representation['vacancy'] = representation.pop('vacancy_data')
        return representation


class EmployeeStatusBulkSerializer(serializers.Serializer):
    """Сериализатор для bulk update статуса сотрудника"""
    employee_id = serializers.IntegerField(required=True)
    status_type = serializers.ChoiceField(
        choices=['in_service', 'vacation', 'sick_leave', 'business_trip', 'training',
                 'competition', 'other_absence', 'on_duty', 'after_duty', 'seconded_from', 'seconded_to'],
        required=False
    )
    state = serializers.ChoiceField(
        choices=['planned', 'active', 'completed', 'cancelled'],
        required=False
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class ChildStaffUnitBulkSerializer(serializers.Serializer):
    """Сериализатор для bulk update дочерних штатных единиц"""
    id = serializers.IntegerField(required=False, allow_null=True)  # None для создания новой
    division = serializers.IntegerField(required=False)
    position = serializers.IntegerField(required=False)
    employee = serializers.IntegerField(required=False, allow_null=True)
    vacancy = serializers.IntegerField(required=False, allow_null=True)
    index = serializers.IntegerField(required=False)
    parent_id = serializers.IntegerField(required=False, allow_null=True)


class StaffUnitBulkUpdateSerializer(serializers.Serializer):
    """
    Bulk update сериализатор для штатной единицы.
    Обновляет саму единицу, дочерние единицы, сотрудников и их статусы.
    """
    # Основные поля штатной единицы
    division = serializers.IntegerField(required=False)
    position = serializers.IntegerField(required=False)
    employee = serializers.IntegerField(required=False, allow_null=True)
    vacancy = serializers.IntegerField(required=False, allow_null=True)
    index = serializers.IntegerField(required=False)
    parent_id = serializers.IntegerField(required=False, allow_null=True)

    # Дочерние штатные единицы
    children = ChildStaffUnitBulkSerializer(many=True, required=False)

    # Обновление статусов сотрудников
    employee_statuses = EmployeeStatusBulkSerializer(many=True, required=False)


class StaffUnitDetailedSerializer(serializers.ModelSerializer):
    """
    Расширенный сериализатор для детального отображения штатной единицы.
    Включает полную информацию о дочерних единицах и сотрудниках.
    """
    # Вложенные объекты для чтения
    division = DivisionSerializer(read_only=True)
    position = DictionaryPositionSerializer(read_only=True)
    employee = EmployeeSerializer(read_only=True)
    vacancy = VacancySerializer(read_only=True)

    # Дочерние штатные единицы (рекурсивно)
    children = serializers.SerializerMethodField()

    # Статусы сотрудника (если есть)
    employee_statuses = serializers.SerializerMethodField()

    class Meta:
        model = StaffUnit
        fields = [
            "id",
            "division",
            "position",
            "employee",
            "vacancy",
            "index",
            "parent_id",
            "children",
            "employee_statuses"
        ]

    def get_children(self, obj):
        """Получить всех дочерних с полной информацией"""
        children = obj.get_children()
        if children:
            # Используем упрощенную версию для дочерних
            return StaffUnitSerializer(children, many=True).data
        return []

    def get_employee_statuses(self, obj):
        """Получить последние статусы сотрудника"""
        if obj.employee:
            statuses = obj.employee.statuses.order_by('-created_at')[:5]
            return EmployeeStatusSerializer(statuses, many=True).data
        return []


class DirectorateStaffUnitSerializer(StaffUnitDetailedSerializer):
    """
    Сериализатор для directorate endpoint.
    Фильтрует children чтобы показывать ТОЛЬКО штатные единицы из того же подразделения.
    """

    def get_children(self, obj):
        """
        Получить дочерние штатные единицы ТОЛЬКО из того же подразделения.
        Для directorate endpoint не показываем штатные единицы из дочерних подразделений.
        """
        # Получаем всех MPTT детей
        children = obj.get_children()

        if children:
            # Фильтруем только тех, кто в том же division
            children_same_division = children.filter(division=obj.division)
            if children_same_division.exists():
                # Рекурсивно используем тот же сериализатор
                return DirectorateStaffUnitSerializer(children_same_division, many=True).data

        return []
