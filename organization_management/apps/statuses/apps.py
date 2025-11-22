"""
Конфигурация приложения statuses
"""
from django.apps import AppConfig


class StatusesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'organization_management.apps.statuses'
    verbose_name = '5. Управление статусами сотрудников'

    def ready(self):
        """Регистрация сигналов при инициализации приложения"""
        import organization_management.apps.statuses.signals  # noqa
