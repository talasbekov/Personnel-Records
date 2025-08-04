from django.apps import AppConfig


class AuditConfig(AppConfig):
    """
    Application configuration for the audit app.

    The audit app does not require any startup hooks, but defining
    ``default_auto_field`` here keeps migrations consistent.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"