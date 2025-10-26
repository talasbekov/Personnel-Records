from .base import *

DEBUG = False

# TODO: Add production domain
ALLOWED_HOSTS = []

# TODO: Configure production database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'prod_db_name',
        'USER': 'prod_db_user',
        'PASSWORD': 'prod_db_password',
        'HOST': 'prod_db_host',
        'PORT': '5432',
    }
}

# Celery
CELERY_BROKER_URL = "redis://prod_redis:6379/0"
CELERY_RESULT_BACKEND = "redis://prod_redis:6379/0"

# Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("prod_redis", 6379)],
        },
    },
}

# Caching
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://prod_redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}
