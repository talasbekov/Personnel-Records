"""
Common app configuration
"""
from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'organization_management.apps.common'
    verbose_name = '1. Роли и Права'
