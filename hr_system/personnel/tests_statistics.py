from django.test import TestCase
from .models import Division, Position, Employee, StaffingUnit, SecondmentRequest, EmployeeStatusLog, EmployeeStatusType, DivisionType
from .services import get_division_statistics
import datetime

class StatisticsCalculationTest(TestCase):
    def setUp(self):
        # --- Create Divisions ---
        self.dep1 = Division.objects.create(name="Department 1", division_type=DivisionType.DEPARTMENT)
        self.man1_dep1 = Division.objects.create(name="Management 1.1", division_type=DivisionType.MANAGEMENT, parent_division=self.dep1)
        self.dep2 = Division.objects.create(name="Department 2", division_type=DivisionType.DEPARTMENT)

        # --- Create Positions ---
        self.manager_pos = Position.objects.create(name="Manager", level=10)
        self.clerk_pos = Position.objects.create(name="Clerk", level=20)

        # --- Define Staffing Plan for Department 1 ---
        # Total Staffing for Dep1 and its children should be 10
        StaffingUnit.objects.create(division=self.dep1, position=self.manager_pos, quantity=2) # 2 Managers in Dep1
        StaffingUnit.objects.create(division=self.man1_dep1, position=self.clerk_pos, quantity=8) # 8 Clerks in Man1.1

        # --- Create Employees for Department 1 ---
        # Total "On List" for Dep1 should be 6
        # 1. In Line-up
        self.emp_in_lineup = Employee.objects.create(full_name="Сотрудник В Строю", division=self.man1_dep1, position=self.clerk_pos, hired_date=datetime.date(2024, 1, 1))
        # 2. On Leave
        self.emp_on_leave = Employee.objects.create(full_name="Сотрудник В Отпуске", division=self.man1_dep1, position=self.clerk_pos, hired_date=datetime.date(2024, 1, 1))
        EmployeeStatusLog.objects.create(employee=self.emp_on_leave, status=EmployeeStatusType.ON_LEAVE, date_from=datetime.date(2025, 1, 1), date_to=datetime.date(2025, 1, 31))
        # 3. Sick
        self.emp_sick = Employee.objects.create(full_name="Сотрудник На Больничном", division=self.man1_dep1, position=self.clerk_pos, hired_date=datetime.date(2024, 1, 1))
        EmployeeStatusLog.objects.create(employee=self.emp_sick, status=EmployeeStatusType.SICK_LEAVE, date_from=datetime.date(2025, 1, 1), date_to=datetime.date(2025, 1, 31))
        # 4. Business Trip
        self.emp_trip = Employee.objects.create(full_name="Сотрудник В Командировке", division=self.man1_dep1, position=self.clerk_pos, hired_date=datetime.date(2024, 1, 1))
        EmployeeStatusLog.objects.create(employee=self.emp_trip, status=EmployeeStatusType.BUSINESS_TRIP, date_from=datetime.date(2025, 1, 1), date_to=datetime.date(2025, 1, 31))
        # 5. Seconded Out
        self.emp_seconded_out = Employee.objects.create(full_name="Сотрудник Откомандирован", division=self.man1_dep1, position=self.clerk_pos, hired_date=datetime.date(2024, 1, 1))
        EmployeeStatusLog.objects.create(employee=self.emp_seconded_out, status=EmployeeStatusType.SECONDED_OUT, date_from=datetime.date(2025, 1, 1), secondment_division=self.dep2)
        # 6. Another In Line-up
        self.emp_in_lineup_2 = Employee.objects.create(full_name="Еще Один В Строю", division=self.dep1, position=self.manager_pos, hired_date=datetime.date(2024, 1, 1))

        # --- Create Employees Seconded INTO Department 1 ---
        # Total Seconded-in for Dep1 should be 2
        emp_to_second_in_1 = Employee.objects.create(full_name="Прикомандированный 1", division=self.dep2, position=self.clerk_pos, hired_date=datetime.date(2024, 1, 1))
        SecondmentRequest.objects.create(employee=emp_to_second_in_1, from_division=self.dep2, to_division=self.dep1, status='APPROVED', date_from=datetime.date(2025, 1, 1))

        emp_to_second_in_2 = Employee.objects.create(full_name="Прикомандированный 2 В Отпуске", division=self.dep2, position=self.clerk_pos, hired_date=datetime.date(2024, 1, 1))
        SecondmentRequest.objects.create(employee=emp_to_second_in_2, from_division=self.dep2, to_division=self.man1_dep1, status='APPROVED', date_from=datetime.date(2025, 1, 1))
        # This seconded-in employee is also on leave
        EmployeeStatusLog.objects.create(employee=emp_to_second_in_2, status=EmployeeStatusType.ON_LEAVE, date_from=datetime.date(2025, 1, 10), date_to=datetime.date(2025, 1, 20))


    def test_division_statistics_calculation(self):
        """
        Tests the main get_division_statistics function with a complex setup.
        """
        test_date = datetime.date(2025, 1, 15)
        stats = get_division_statistics(self.dep1, test_date)

        # --- Verify top-level numbers ---
        self.assertEqual(stats['total_staffing'], 10, "Total staffing should be sum of all units in division and sub-divisions.")
        self.assertEqual(stats['on_list_count'], 6, "On list count should be all employees homed in the division.")
        self.assertEqual(stats['vacant_count'], 4, "Vacant should be staffing minus on-list.")
        self.assertEqual(stats['seconded_in_count'], 2, "Seconded-in count should be 2.")
        self.assertEqual(stats['in_lineup_count'], 2, "In line-up count should be 2.")

        # --- Verify status counts for 'on list' employees ---
        status_counts = stats['status_counts']
        self.assertEqual(status_counts.get(EmployeeStatusType.ON_DUTY_SCHEDULED, 0), 2)
        self.assertEqual(status_counts.get(EmployeeStatusType.ON_LEAVE, 0), 1)
        self.assertEqual(status_counts.get(EmployeeStatusType.SICK_LEAVE, 0), 1)
        self.assertEqual(status_counts.get(EmployeeStatusType.BUSINESS_TRIP, 0), 1)
        self.assertEqual(status_counts.get(EmployeeStatusType.SECONDED_OUT, 0), 1)

        # --- Verify formula: По списку = сумма всех статусов ---
        self.assertEqual(stats['on_list_count'], sum(status_counts.values()))

        # --- Verify status counts for 'seconded-in' employees ---
        # We expect one to be 'in line-up' and one to be 'on leave'
        seconded_status_counts = stats['seconded_in_status_counts']
        self.assertEqual(seconded_status_counts.get(EmployeeStatusType.ON_DUTY_SCHEDULED, 0), 1)
        self.assertEqual(seconded_status_counts.get(EmployeeStatusType.ON_LEAVE, 0), 1)
        self.assertEqual(sum(seconded_status_counts.values()), 2)


import io
from docx import Document
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from .models import UserProfile, UserRole

class ReportGenerationTest(APITestCase):
    def setUp(self):
        self.dep = Division.objects.create(name="Report Test Dep", division_type=DivisionType.DEPARTMENT)
        self.user = User.objects.create_user(username='testuser', password='password')
        # Create a UserProfile for the test user to satisfy permission checks
        UserProfile.objects.create(user=self.user, role=UserRole.ROLE_4)
        self.client.force_authenticate(user=self.user)

    def test_report_endpoint_returns_docx_file(self):
        """
        Tests that the /report endpoint returns a valid .docx file response.
        """
        url = f'/api/personnel/divisions/{self.dep.id}/report/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertIn('attachment; filename=', response['Content-Disposition'])

        # --- Verify the document content ---
        # Load the response content into a document object
        doc_buffer = io.BytesIO(response.content)
        document = Document(doc_buffer)

        # Check the title
        title_text = document.paragraphs[0].text
        self.assertIn("Report Test Dep", title_text)
        self.assertIn("САПТЫҚ ТІЗІМІ", title_text)

        # Check that a table was created
        self.assertTrue(len(document.tables) > 0, "The report should contain a table.")

        # Check table headers
        table = document.tables[0]
        headers = [cell.text for cell in table.rows[0].cells]
        self.assertIn("Количество по списку", headers)
        self.assertIn("В строю", headers)
