"""
Custom DRF throttling classes for the personnel application.

This module defines a role‑based rate throttle that constrains the number
of API requests a user may make within a time window based on their
assigned role.  The values used here are illustrative defaults and
should be tuned according to actual load expectations and business
requirements.  See the technical specification for guidance on
role‑specific rate limits and adjust accordingly.

Example usage:

In your Django REST Framework settings (settings.py), add the following:

```
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'hr_system.personnel.throttles.RoleRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Fallback rates can remain empty; RoleRateThrottle sets its own rates.
    },
}
```

This will apply the role‑based throttling across all API endpoints.  You
can also apply the throttle on a per‑view basis by adding it to the
`throttle_classes` attribute of your view or viewset.
"""

from rest_framework.throttling import SimpleRateThrottle

try:
    # Import UserRole dynamically; this import will fail at import
    # time during migrations, so wrap in try/except.
    from .models import UserRole
except Exception:  # pragma: no cover
    UserRole = None  # type: ignore


class RoleRateThrottle(SimpleRateThrottle):
    """Rate limit API requests based on the caller's role.

    For each authenticated user, a cache key is constructed from the
    user's role identifier.  The `rate` attribute is set dynamically
    according to the role before delegating to the parent class.  If no
    role is available (e.g. unauthenticated requests or missing profile),
    throttling is bypassed by returning `None` from `get_cache_key`.
    """

    scope = "role"

    def _get_role(self, request):
        """Safely retrieve the numeric role from the request's user profile."""
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not UserRole:  # type: ignore[truthy-bool]
            return None
        try:
            return getattr(user.profile, "role", None)
        except Exception:
            return None

    def get_cache_key(self, request, view):  # type: ignore[override]
        role = self._get_role(request)
        if role is None:
            return None
        # Use the numeric value of the role as the cache identifier.
        ident = str(role.value) if hasattr(role, "value") else str(role)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view):  # type: ignore[override]
        role = self._get_role(request)
        if role is None:
            return True  # No role: disable throttling for unauthenticated or missing roles
        # Define per‑role rates.  Adjust these values based on the spec.
        # Format: "number/period", where period can be s, m, h or d.
        default_rates = {
            # Role 1: read‑only; very low write throughput
            getattr(UserRole, "ROLE_1", None): "30/min",
            # Role 2: department head; moderate volume
            getattr(UserRole, "ROLE_2", None): "60/min",
            # Role 3: management division; frequent writes
            getattr(UserRole, "ROLE_3", None): "120/min",
            # Role 4: system admin; high throughput
            getattr(UserRole, "ROLE_4", None): "300/min",
            # Role 5: HR admin; high throughput but less than system admin
            getattr(UserRole, "ROLE_5", None): "180/min",
            # Role 6: office/department head; lower volume than Role 3
            getattr(UserRole, "ROLE_6", None): "60/min",
        }
        # Look up the rate for the current role; fall back to a default
        self.rate = default_rates.get(role, "60/min")
        return super().allow_request(request, view)


class AuthRateThrottle(SimpleRateThrottle):
    """Throttle for authentication attempts.

    Limits login or token‑related endpoints to 5 requests per minute to
    mitigate brute‑force attacks.  Use this throttle on views handling
    authentication or password reset.
    """

    scope = "auth"
    rate = "5/min"


class ReportGenerationThrottle(SimpleRateThrottle):
    """Throttle for report/document generation endpoints.

    Constrains document generation to 10 requests per hour per user to
    prevent resource exhaustion when exporting large reports.
    """

    scope = "report"
    rate = "10/hour"


class SearchRateThrottle(SimpleRateThrottle):
    """Throttle for search endpoints.

    Allows up to 200 search queries per minute per user.  Apply this
    throttle to views that perform search or filter operations on
    large datasets to avoid performance degradation.
    """

    scope = "search"
    rate = "200/min"