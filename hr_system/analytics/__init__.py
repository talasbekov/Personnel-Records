"""
Analytics application initialization.

This package provides simple reporting and KPI endpoints that aggregate
data from the personnel system.  It is intentionally lightweight and
read‑only: the views collect statistics on demand rather than storing
any additional state in the database.  To use these endpoints add
``'analytics'`` to ``INSTALLED_APPS`` in your Django settings and
include ``analytics.urls`` in your project's URL configuration.
"""
