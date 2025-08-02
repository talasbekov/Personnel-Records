from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        # Import signal handlers if they exist
        try:
            import notifications.signals  # noqa: F401
        except ImportError:
            pass
