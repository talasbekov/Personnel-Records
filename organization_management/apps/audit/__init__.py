"""
Audit package for the HR system.

Provides an audit log model, middleware to record CRUD operations and
API views to query log entries.  The audit log records the acting
user, target object and a JSON payload containing additional context
such as a diff of changed fields.  Use the provided middleware by
adding ``audit.middleware.AuditMiddleware`` to ``MIDDLEWARE`` in
settings.
"""
