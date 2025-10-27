from organization_management.apps.employees.models import Employee
from organization_management.apps.auth.models import User

class EmployeeApplicationService:
    def hire_employee(self, validated_data):
        """
        Прием на работу нового сотрудника.
        """
        # Создаем сотрудника
        employee = Employee.objects.create(**validated_data)

        # Создаем пользователя, если нужно
        if validated_data.get('create_user', False):
            user = User.objects.create_user(
                username=f"user_{employee.personnel_number}",
                password=validated_data.get('password', 'password'),
                first_name=employee.first_name,
                last_name=employee.last_name,
                email=employee.work_email or employee.personal_email,
            )
            employee.user = user
            employee.save()

        return employee
