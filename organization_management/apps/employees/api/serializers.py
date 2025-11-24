from rest_framework import serializers
from organization_management.apps.employees.models import Employee
from organization_management.apps.dictionaries.api.serializers import RankSerializer

class EmployeeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Employee.
    """
    rank_detail = RankSerializer(source='rank', read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = '__all__'

    def get_photo_url(self, obj: Employee) -> str:
        """Возвращает URL фото сотрудника"""
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None
