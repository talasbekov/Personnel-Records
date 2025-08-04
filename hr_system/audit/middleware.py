"""
Middleware to record audit log entries for API requests.

This middleware intercepts POST/PUT/PATCH/DELETE requests to API
endpoints and records an ``AuditLog`` entry capturing the action type,
user, target object and any differences in the object's state.  It
also stores request metadata such as IP address and user agent.  The
middleware must be added to the ``MIDDLEWARE`` list in settings to
take effect.
"""

import json
from django.utils.deprecation import MiddlewareMixin
from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict
from .models import AuditLog


class AuditMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

    def __call__(self, request):
        # Capture pre‑update state for PUT/PATCH to compute diffs later
        request.audit_pre_update_state = None
        if request.method in ["PUT", "PATCH"]:
            try:
                parts = request.path.strip("/").split("/")
                if len(parts) >= 4 and parts[0] == "api":
                    app_label = parts[1]
                    model_name_plural = parts[2]
                    model_name = model_name_plural.rstrip("s")
                    object_id = parts[3]
                    content_type = ContentType.objects.get(
                        app_label=app_label, model=model_name
                    )
                    model_class = content_type.model_class()
                    instance = model_class.objects.get(pk=object_id)
                    request.audit_pre_update_state = model_to_dict(instance)
            except Exception:
                # Ignore any errors obtaining pre state
                pass
        response = self.get_response(request)
        # Only audit successful API requests
        if not request.path.startswith("/api/") or not (200 <= response.status_code < 300):
            return response
        user = request.user if request.user.is_authenticated else None
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        session_id = request.session.session_key
        # Determine action type based on method
        action_map = {
            "POST": "CREATE",
            "PUT": "UPDATE",
            "PATCH": "UPDATE",
            "DELETE": "DELETE",
        }
        action_type = action_map.get(request.method)
        if not action_type:
            return response
        payload = {}
        target_object_id = None
        content_type = None
        # For CREATE/UPDATE the object id is returned in the JSON response
        if response.content and response.get("Content-Type") == "application/json":
            try:
                response_data = json.loads(response.content)
                if isinstance(response_data, dict):
                    target_object_id = response_data.get("id")
            except json.JSONDecodeError:
                response_data = {}
        # Determine the content type from the URL
        parts = request.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "api":
            app_label = parts[1]
            model_name_plural = parts[2]
            model_name = model_name_plural.rstrip("s")
            try:
                content_type = ContentType.objects.get(
                    app_label=app_label, model=model_name
                )
            except ContentType.DoesNotExist:
                content_type = None
        # For DELETE requests the object id is part of the URL
        if action_type == "DELETE" and len(parts) >= 4:
            target_object_id = parts[3]
        # Compute field diffs for UPDATE actions
        if (
            action_type == "UPDATE"
            and request.audit_pre_update_state
            and content_type
            and target_object_id
        ):
            try:
                model_class = content_type.model_class()
                instance = model_class.objects.get(pk=target_object_id)
                post_update_state = model_to_dict(instance)
                pre_update_state = request.audit_pre_update_state
                diff = {
                    "old": {
                        k: v
                        for k, v in pre_update_state.items()
                        if str(v) != str(post_update_state.get(k))
                    },
                    "new": {
                        k: v
                        for k, v in post_update_state.items()
                        if str(v) != str(pre_update_state.get(k))
                    },
                }
                # Remove entries with only type differences
                for k in list(diff["old"].keys()):
                    if k not in diff["new"]:
                        del diff["old"][k]
                payload["diff"] = diff
            except Exception:
                pass
        # Create the audit log entry if we have enough information
        if content_type and target_object_id:
            AuditLog.objects.create(
                user=user,
                action_type=action_type,
                content_type=content_type,
                object_id=target_object_id,
                payload=payload,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
            )
        return response