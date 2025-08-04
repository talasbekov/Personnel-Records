"""
Celery application configuration for the hr_system project.

This module sets up the Celery application and instructs it to read
configuration from the Django settings module using the ``CELERY_`` prefix.
It also auto‑discovers task modules across all installed Django apps.

Having a separate ``celery.py`` file allows Celery to be initialised
without importing the entire Django stack, which helps avoid side
effects during process startup.  See Django/Celery documentation for
additional details.
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hr_system.settings")

app = Celery("hr_system")

# Using a string here means the worker doesn't need to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """A simple debug task that prints its request information."""
    print(f"Request: {self.request!r}")
