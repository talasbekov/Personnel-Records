from rest_framework import serializers
from organization_management.apps.divisions.models import Division

class RecursiveDivisionSerializer(serializers.Serializer):
    """
    Рекурсивный сериализатор для отображения дерева подразделений.
    """
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data

class DivisionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Division.
    """
    children = RecursiveDivisionSerializer(many=True, read_only=True)

    class Meta:
        model = Division
        fields = ('id', 'name', 'code', 'division_type', 'parent', 'children')
