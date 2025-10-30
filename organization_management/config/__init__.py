"""
Initialisation for the organization_management Django project.

This module conditionally imports the Celery application so that tasks
are auto‑discovered when Celery workers are running.  The import is
wrapped in a ``try`` block to avoid raising a ``ModuleNotFoundError``
in environments where Celery is not installed (e.g. during local
development or documentation builds).
"""

try:
    from .celery import app as celery_app  # noqa: F401
except ModuleNotFoundError:
    # Celery is optional; if not installed tasks will not be registered
    celery_app = None  # type: ignore

__all__ = ["celery_app"]
