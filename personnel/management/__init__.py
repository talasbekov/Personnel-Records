"""
Management package for the personnel application.

This package exposes custom management commands used for periodic
maintenance tasks such as copying employee statuses forward to
subsequent days and checking whether divisions have updated their
status indicators.  Having an explicit ``management`` package
structure makes it possible to invoke these commands via
``django.core.management.call_command`` and also allows Celery tasks
to re‑use them as part of scheduled jobs.
"""
