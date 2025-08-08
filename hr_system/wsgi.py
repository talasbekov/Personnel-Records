"""
WSGI config for the HR system project.

This file exposes the WSGI callable as a module‑level variable named
``application``.  It is used by Django's ``runserver`` command as well
as any production WSGI server such as Gunicorn.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hr_system.settings")

application = get_wsgi_application()