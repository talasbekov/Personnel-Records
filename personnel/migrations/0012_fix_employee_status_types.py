from django.db import migrations


def update_status_types(apps, schema_editor):
    """Обновляем существующие статусы для соответствия ТЗ"""
    EmployeeStatusLog = apps.get_model('personnel', 'EmployeeStatusLog')

    # Переименовываем ON_DUTY в ON_DUTY_ACTUAL если есть
    EmployeeStatusLog.objects.filter(status='ON_DUTY').update(status='ON_DUTY_ACTUAL')

    # Переименовываем IN_LINEUP в ON_DUTY_SCHEDULED если есть
    EmployeeStatusLog.objects.filter(status='IN_LINEUP').update(status='ON_DUTY_SCHEDULED')


def reverse_status_types(apps, schema_editor):
    """Откат изменений"""
    EmployeeStatusLog = apps.get_model('personnel', 'EmployeeStatusLog')

    EmployeeStatusLog.objects.filter(status='ON_DUTY_ACTUAL').update(status='ON_DUTY')
    EmployeeStatusLog.objects.filter(status='ON_DUTY_SCHEDULED').update(status='IN_LINEUP')


class Migration(migrations.Migration):
    dependencies = [
        ('personnel', '0011_add_missing_fields_and_models'),
    ]

    operations = [
        migrations.RunPython(update_status_types, reverse_status_types),
    ]
