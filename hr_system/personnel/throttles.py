"""
Custom DRF throttling classes for the personnel application.

This module defines a role‑based rate throttle that constrains the number
of API requests a user may make within a time window based on their
assigned role. See the technical specification for role-specific limits.
"""

from rest_framework.throttling import SimpleRateThrottle

try:
    from .models import UserRole
except Exception:  # during migrations
    UserRole = None


class RoleRateThrottle(SimpleRateThrottle):
    """Throttle based on user's role."""
    scope = "role"

    def _get_role(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not UserRole:
            return None
        try:
            return getattr(user.profile, "role", None)
        except Exception:
            return None

    def get_cache_key(self, request, view):
        role = self._get_role(request)
        if role is None:
            return None
        ident = str(role.value) if hasattr(role, "value") else str(role)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view):
        role = self._get_role(request)
        if role is None:
            return True
        default_rates = {
            getattr(UserRole, "ROLE_1", None): "30/min",
            getattr(UserRole, "ROLE_2", None): "60/min",
            getattr(UserRole, "ROLE_3", None): "120/min",
            getattr(UserRole, "ROLE_4", None): "300/min",
            getattr(UserRole, "ROLE_5", None): "180/min",
            getattr(UserRole, "ROLE_6", None): "60/min",
        }
        self.rate = default_rates.get(role, "60/min")
        return super().allow_request(request, view)


class AuthRateThrottle(SimpleRateThrottle):
    """Throttle for login/authentication attempts."""
    scope = "auth"
    rate = "5/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request)
        }


class ReportGenerationThrottle(SimpleRateThrottle):
    """Throttle for report/document generation."""
    scope = "report"
    rate = "10/hour"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return self.cache_format % {
                "scope": self.scope,
                "ident": request.user.pk
            }
        return None


class SearchRateThrottle(SimpleRateThrottle):
    """Throttle for search/filter queries."""
    scope = "search"
    rate = "200/min"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return self.cache_format % {
                "scope": self.scope,
                "ident": request.user.pk
            }
        return None
