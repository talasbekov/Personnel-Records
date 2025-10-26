from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from organization_management.apps.audit.models import AuditLog
from organization_management.apps.divisions.models import Division, DivisionType

class AuditLogModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.division = Division.objects.create(name='Test Division', division_type=DivisionType.DEPARTMENT)

    def test_create_audit_log(self):
        """
        Test that an AuditLog entry can be created successfully.
        """
        log_entry = AuditLog.objects.create(
            user=self.user,
            action_type='CREATE',
            target_object=self.division,
            payload={'details': 'Division created'},
            ip_address='127.0.0.1',
            user_agent='Test Client'
        )

        self.assertEqual(AuditLog.objects.count(), 1)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.action_type, 'CREATE')
        self.assertEqual(log_entry.target_object, self.division)
        self.assertEqual(log_entry.content_type, ContentType.objects.get_for_model(self.division))
        self.assertEqual(log_entry.object_id, self.division.id)
        self.assertEqual(log_entry.payload, {'details': 'Division created'})
        self.assertEqual(log_entry.ip_address, '127.0.0.1')
        self.assertEqual(log_entry.user_agent, 'Test Client')
