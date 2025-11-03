from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """
    Configuration for the notifications app.

    Ensures that signal handlers are imported when the app is ready so
    that model events generate corresponding notifications.  Uses the
    ``ready`` hook to avoid import side effects during startup.
    """
    print("LOADING NOTIFICATIONS APP")
    default_auto_field = "django.db.models.BigAutoField"
    name = "organization_management.apps.notifications"

    def ready(self):  # pragma: no cover
        # Import signal handlers.  Any ImportError is silently ignored
        # to allow the project to run even if optional dependencies are
        # unavailable (e.g. Channels).
        try:
            import organization_management.apps.notifications.signals  # noqa: F401
        except Exception:
            pass