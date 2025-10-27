from rest_framework import serializers
from rest_framework_recursive.fields import RecursiveField
from organization_management.apps.divisions.models import Division

class DivisionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Division.
    Использует рекурсивное поле для отображения дочерних подразделений.
    """
    children = serializers.ListField(read_only=True, source='get_children')

    class Meta:
        model = Division
        fields = (
            'id',
            'name',
            'code',
            'division_type',
            'parent',
            'is_active',
            'order',
            'children',
        )

    def get_children(self, obj):
        """
        Рекурсивно сериализует дочерние подразделения.
        """
        return DivisionSerializer(obj.get_children(), many=True).data
