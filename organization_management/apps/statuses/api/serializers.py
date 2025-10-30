from rest_framework import serializers
from organization_management.apps.statuses.models import EmployeeStatus


class EmployeeStatusSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели EmployeeStatus.
    Выполняет полную валидацию модели (clean) для проверки пересечений интервалов.
    """

    class Meta:
        model = EmployeeStatus
        fields = '__all__'

    def validate(self, attrs):
        # Создаем временный объект модели и вызываем clean()
        # Чтобы корректно отработал update, учитываем instance
        instance = self.instance or EmployeeStatus()
        for k, v in attrs.items():
            setattr(instance, k, v)
        # при partial update нужно заполнить недостающие обязательные поля из instance
        # вызов clean() поднимет ValidationError при пересечениях
        instance.clean()
        return attrs
