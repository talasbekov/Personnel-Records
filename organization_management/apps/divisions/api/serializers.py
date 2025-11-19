from typing import List, Dict, Any
from rest_framework import serializers
from rest_framework_recursive.fields import RecursiveField
from drf_spectacular.utils import extend_schema_field
from organization_management.apps.divisions.models import Division

class DivisionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Division.
    Использует рекурсивное поле для отображения дочерних подразделений.
    """
    children = serializers.SerializerMethodField(read_only=True)

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

    @extend_schema_field(serializers.ListSerializer(child=serializers.DictField()))
    def get_children(self, obj) -> List[Dict[str, Any]]:
        """
        Рекурсивно сериализует дочерние подразделения.
        """
        return DivisionSerializer(obj.get_children(), many=True).data
