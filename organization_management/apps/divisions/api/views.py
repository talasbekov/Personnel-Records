from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from organization_management.apps.divisions.application.services import DivisionApplicationService
from .serializers import DivisionSerializer
from organization_management.apps.employees.api.serializers import EmployeeSerializer

class DivisionViewSet(viewsets.ViewSet):
    """
    ViewSet для управления подразделениями.
    Делегирует всю бизнес-логику в DivisionApplicationService.
    """
    permission_classes = [IsAuthenticated]
    service = DivisionApplicationService()

    def list(self, request):
        divisions = self.service.get_all_divisions()
        serializer = DivisionSerializer(divisions, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        division = self.service.get_division_by_id(int(pk))
        serializer = DivisionSerializer(division)
        return Response(serializer.data)

    def create(self, request):
        serializer = DivisionSerializer(data=request.data)
        if serializer.is_valid():
            division = self.service.create_division(**serializer.validated_data)
            return Response(DivisionSerializer(division).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        serializer = DivisionSerializer(data=request.data)
        if serializer.is_valid():
            division = self.service.update_division(int(pk), **serializer.validated_data)
            return Response(DivisionSerializer(division).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        self.service.delete_division(int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        tree = self.service.get_division_tree()
        serializer = DivisionSerializer(tree, many=True) # Здесь нужен рекурсивный сериализатор
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def employees(self, request, pk=None):
        division = self.service.get_division_by_id(int(pk))
        employees = division.employees.all()
        serializer = EmployeeSerializer(employees, many=True)
        return Response(serializer.data)
