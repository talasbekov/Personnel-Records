"""
Django settings for hr_system project.

This settings file is based on the original repository configuration but includes
several enhancements to address missing functionality identified in the
technical audit.  The key additions include:

* Configuration for Django Channels to enable WebSocket support via the
  ``CHANNEL_LAYERS`` setting.  The in‑memory channel layer is used by
  default, which requires no external services and suffices for
  development/testing environments.  In production you should switch to
  ``channels_redis.core.RedisChannelLayer`` and configure a Redis server.

* A simple caching backend using Django's local memory cache.  This is
  activated via the ``CACHES`` dictionary and helps speed up read‑heavy
  views when combined with the ``cache_page`` decorator.  You can
  replace this with a Redis or Memcached backend for greater scalability.

* Celery broker and result backend settings along with a basic beat
  schedule.  The schedule defines two periodic tasks – one that copies
  employee statuses forward to cover weekends and another that checks
  whether divisions have updated their status logs on time.  Both
  tasks are defined in ``personnel/tasks.py`` and executed via
  ``celery beat``.

These additions are necessary to satisfy the real‑time and background
processing requirements outlined in the specification.  Feel free to
customise values such as Redis hosts/ports, broker URLs or cache
backends to suit your deployment environment.
"""

from pathlib import Path
from datetime import timedelta
import os

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
# NOTE: replace this key in production
SECRET_KEY = "django-insecure-dummy-key-for-now"
DEBUG = True  # Set to False in production
ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    "daphne",  # ASGI server for channels
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_yasg",
    "rest_framework_simplejwt",
    "django_filters",
    "personnel",
    "audit",
    "notifications",
    "channels",
    "analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "audit.middleware.AuditMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "hr_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hr_system.wsgi.application"
ASGI_APPLICATION = "hr_system.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"

# Media and file storage configuration.  Use MinIO/S3 compatible
# storage backend for photos and generated reports.  In production,
# supply the appropriate environment variables or override these
# settings in a local settings file.  Bucket names and credentials
# below are placeholders.
MEDIA_URL = "/media/"
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "http://minio:9000")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "hr-media")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_DEFAULT_ACL = None

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    # Enable filtering support via django_filters on list endpoints
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "personnel.throttles.RoleRateThrottle",
    ],
    # Rate limits are deliberately generous to allow for internal API usage;
    # tune them in production as necessary.
    "DEFAULT_THROTTLE_RATES": {
        'role': '100/hour',
        'user': '1000/day',
        'anon': '50/day',
    },

}

# Simple JWT settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Формат: Bearer {ваш access токен}",
        }
    },
    "USE_SESSION_AUTH": False,
    "DEFAULT_INFO": "hr_system.urls.api_info",
}


# Caching configuration – using local memory cache by default.
# For production environments consider using Memcached or Redis for better
# performance and persistence.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-hr-system-cache",
    }
}

# Default cache timeout (in seconds) used by cache_page decorators.
CACHE_TIMEOUT = 60 * 5  # five minutes; adjust as necessary

# Sessions stored in cache for improved performance
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Channels configuration – using InMemoryChannelLayer by default.  Switch to
# channels_redis.core.RedisChannelLayer in production and configure hosts.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Celery configuration
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Copy statuses every day shortly after midnight.  This schedule will
    # propagate status logs forward and ensure employees retain their most
    # recent status during weekends.
    "copy_statuses_daily": {
        "task": "personnel.tasks.copy_statuses_task",
        "schedule": crontab(minute=5, hour=0),
    },
    # Run the check for overdue status updates multiple times per day to
    # implement automatic escalation reminders.  According to the
    # specification, escalations should occur at 14:00, 16:00 and 18:00.
    "check_status_updates_14": {
        "task": "personnel.tasks.check_status_updates_task",
        "schedule": crontab(minute=0, hour=14),
    },
    "check_status_updates_16": {
        "task": "personnel.tasks.check_status_updates_task",
        "schedule": crontab(minute=0, hour=16),
    },
    "check_status_updates_18": {
        "task": "personnel.tasks.check_status_updates_task",
        "schedule": crontab(minute=0, hour=18),
    },
    # Copy statuses after the work day ends (e.g. 18:10) to carry
    # forward any statuses for the next day.  This helps ensure that
    # employees who have not had their statuses manually updated retain
    # their last known status.
    "copy_statuses_after_18": {
        "task": "personnel.tasks.copy_statuses_task",
        "schedule": crontab(minute=10, hour=18),
    },
    # Reset employees to the default status if their previous status
    # period has expired.  Runs shortly after midnight every day.
    "reset_default_statuses": {
        "task": "personnel.tasks.reset_default_statuses_task",
        "schedule": crontab(minute=10, hour=0),
    },
}
