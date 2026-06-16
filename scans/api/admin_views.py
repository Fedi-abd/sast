"""Staff-only admin API: the data layer behind the SPA's Admin console.

Five endpoint groups, mirroring the console's five tabs:

  - /api/admin/sonarqube/        GET + PUT, plus POST .../test/
  - /api/admin/limits/           GET + bulk PATCH
  - /api/admin/usage/            GET (cross-user scan audit log)
  - /api/admin/users/            GET, PATCH <id>/, POST <id>/reset-password/
  - /api/admin/settings/         GET + PATCH (deployment flags)

All views require `is_staff` (DRF's `IsAdminUser`). The SPA hides the
console from non-staff users, but that's cosmetic; these permissions
are the actual gate.

Security conventions:
  - The Sonar token NEVER leaves the server. Responses carry only
    `token_last4` + `has_token`; PUT treats an absent/empty token as
    "keep the current one".
  - Staff can't deactivate their own account (lockout protection).
  - Password reset returns a one-time temporary password in the
    response instead of emailing a link. The platform has no SMTP
    (email is out of scope), so the admin hands it over directly.
    Django rotates the session auth hash on password change, which
    force-logs-out the affected user everywhere.
"""
import requests
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings as django_settings

from scans.models import PlatformSettings, Scan, SonarSettings
from users.models import PasswordResetRequest, UserProfile

from .serializers import annotate_finding_count

# /api/issues/search accepts only these three; SECURITY_HOTSPOT moved
# to its own endpoint in modern SonarQube and the adapter always
# fetches it separately, so it isn't a configurable type here.
SONAR_ISSUE_TYPE_CHOICES = ["VULNERABILITY", "BUG", "CODE_SMELL"]


def _effective_sonar_config():
    """Merge the SonarSettings row with its env-var fallbacks."""
    row = SonarSettings.get_solo()
    host = row.host or django_settings.SONAR_HOST
    token = row.token or (django_settings.SONAR_TOKEN or "")
    issue_types_raw = row.issue_types or django_settings.SAST_SONAR_ISSUE_TYPES
    issue_types = [t for t in issue_types_raw.split(",") if t]
    return row, host, token, issue_types


def _sonar_config_payload():
    row, host, token, issue_types = _effective_sonar_config()
    return {
        "host": host,
        "token_last4": token[-4:] if token else "",
        "has_token": bool(token),
        "issue_types": issue_types,
        "include_hotspots": row.include_hotspots,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


class SonarConfigWriteSerializer(serializers.Serializer):
    """PUT body for the shared SonarQube config.

    `token` is write-only by design: omitted or empty means "keep the
    stored token", so the UI never has to round-trip the secret.
    """

    host = serializers.URLField(required=False, allow_blank=True)
    token = serializers.CharField(required=False, allow_blank=True)
    issue_types = serializers.ListField(
        child=serializers.ChoiceField(choices=SONAR_ISSUE_TYPE_CHOICES),
        required=False,
    )
    include_hotspots = serializers.BooleanField(required=False)


class AdminSonarConfigView(APIView):
    """GET/PUT /api/admin/sonarqube/: platform-wide Sonar config."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(_sonar_config_payload())

    def put(self, request):
        payload = SonarConfigWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        row = SonarSettings.get_solo()
        if "host" in data:
            row.host = data["host"]
        if data.get("token"):
            row.token = data["token"]
        if "issue_types" in data:
            row.issue_types = ",".join(data["issue_types"])
        if "include_hotspots" in data:
            row.include_hotspots = data["include_hotspots"]
        row.updated_by = request.user.username
        row.save()
        return Response(_sonar_config_payload())


class AdminSonarTestView(APIView):
    """POST /api/admin/sonarqube/test/: verify reachability AND the token.

    Body (optional): ``{host?, token?}``, overrides for testing the
    values currently typed in the form before saving them; absent
    fields fall back to the saved/effective config.

    Uses SonarQube's `/api/authentication/validate` rather than the
    status endpoint, because status answers without auth. A garbage
    token would still report "ok". Always returns 200 with an
    {ok, detail} verdict; a down server or bad token is a *result*,
    not an API error.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        _, host, token, _ = _effective_sonar_config()
        host = (request.data.get("host") or host).rstrip("/")
        if request.data.get("token"):
            token = request.data["token"]

        # `server` / `token` are separate verdicts so the console can
        # light each one green or red on its own; `token: None` means
        # "couldn't be judged" (server down, or a non-Sonar response).
        try:
            if not token:
                # No token configured; check reachability, but a tokenless
                # config can't upload scans, so the verdict is still "not ok".
                response = requests.get(f"{host}/api/system/status", timeout=5)
                server_up = response.status_code == 200
                return Response({
                    "ok": False,
                    "server": server_up,
                    "token": False,
                    "detail": (
                        "no token configured"
                        if server_up
                        else f"HTTP {response.status_code} from {host}"
                    ),
                })

            response = requests.get(
                f"{host}/api/authentication/validate",
                auth=(token, ""),
                timeout=5,
            )
            if response.status_code != 200:
                return Response({
                    "ok": False,
                    "server": True,
                    "token": None,
                    "detail": f"HTTP {response.status_code} from {host}",
                })
            if response.json().get("valid"):
                return Response({
                    "ok": True, "server": True, "token": True,
                    "detail": "token valid",
                })
            return Response({
                "ok": False, "server": True, "token": False,
                "detail": "token INVALID",
            })
        except requests.RequestException as err:
            return Response({
                "ok": False, "server": False, "token": None,
                "detail": f"can't reach {host}: {err}",
            })
        except requests.JSONDecodeError:
            return Response({
                "ok": False,
                "server": True,
                "token": None,
                "detail": f"Unexpected response from {host}. Is that a SonarQube server?",
            })


def _limits_row(user):
    profile = getattr(user, "profile", None)
    return {
        "user_id": user.id,
        "username": user.username,
        "credits": profile.credits if profile else UserProfile.DEFAULT_CREDITS,
        "max_projects": profile.max_projects if profile else UserProfile.DEFAULT_MAX_PROJECTS,
        "max_upload_mb": profile.max_upload_mb if profile else UserProfile.DEFAULT_MAX_UPLOAD_MB,
    }


class LimitsRowSerializer(serializers.Serializer):
    """One row of the bulk limits PATCH. Absent fields stay unchanged.

    `-1` is the "unlimited" sentinel; the UI sends it for a blank field.
    """

    user_id = serializers.IntegerField()
    credits = serializers.IntegerField(required=False, min_value=-1)
    max_projects = serializers.IntegerField(required=False, min_value=-1)
    max_upload_mb = serializers.IntegerField(required=False, min_value=-1)


class AdminLimitsView(APIView):
    """GET/PATCH /api/admin/limits/: per-user quota table.

    PATCH takes ``{"users": [{user_id, credits?, ...}, ...]}`` and is
    all-or-nothing: an unknown user_id or invalid value rolls back the
    whole batch, matching the console's single save bar.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        users = (
            get_user_model().objects
            .select_related("profile")
            .order_by("username")
        )
        return Response([_limits_row(u) for u in users])

    def patch(self, request):
        rows = LimitsRowSerializer(data=request.data.get("users", []), many=True)
        rows.is_valid(raise_exception=True)

        # Pre-flight: fail the whole batch on an unknown user_id
        # before opening the transaction.
        User = get_user_model()
        ids = [row["user_id"] for row in rows.validated_data]
        users_by_id = {u.pk: u for u in User.objects.filter(pk__in=ids)}
        missing = [i for i in ids if i not in users_by_id]
        if missing:
            return Response(
                {"detail": f"Unknown user_id {missing[0]}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = []
        with transaction.atomic():
            for row in rows.validated_data:
                user = users_by_id[row["user_id"]]
                profile, _ = UserProfile.objects.get_or_create(user=user)
                changed = [
                    field for field in ("credits", "max_projects", "max_upload_mb")
                    if field in row
                ]
                for field in changed:
                    setattr(profile, field, row[field])
                if changed:
                    profile.save(update_fields=changed)
                updated.append(_limits_row(user))
        return Response({"users": updated})


class AdminUsageView(APIView):
    """GET /api/admin/usage/: recent scans across ALL users.

    The audit lens: same scan shape as /api/scans/ plus the owner's
    username. `limit` defaults to 50 (the console shows a page, not
    the full history); invalid values 400 like /api/findings/.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        limit_raw = request.query_params.get("limit", "50")
        try:
            limit = int(limit_raw)
            if limit < 1:
                raise ValueError
        except ValueError:
            return Response(
                {"detail": "limit must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scans = annotate_finding_count(
            Scan.objects
            .select_related("project", "project__owner")
            .order_by("-started_at")
        )[:limit]
        return Response([
            {
                "id": str(scan.id),
                "username": scan.project.owner.username,
                "project_name": scan.project.name,
                "tool": scan.tool,
                "tool_display": scan.get_tool_display(),
                "status": scan.status,
                "duration_seconds": scan.duration_seconds,
                "finding_count": scan.finding_count,
                "started_at": scan.started_at.isoformat(),
                # The audit lens doubles as the admin's debugging view;
                # users see a softened failure message, admins see this.
                "error_message": scan.error_message,
            }
            for scan in scans
        ])


def _user_row(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
    }


class UserActiveSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class AdminUsersView(APIView):
    """GET /api/admin/users/: the user-management roster."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        users = get_user_model().objects.order_by("username")
        return Response([_user_row(u) for u in users])


class AdminUserDetailView(APIView):
    """PATCH /api/admin/users/<id>/: toggle is_active.

    Deactivate-not-delete, per the console design. `is_staff` is
    deliberately NOT writable here; promoting staff stays a
    superuser action in the Django admin.
    """

    permission_classes = [IsAdminUser]

    def patch(self, request, user_id):
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        payload = UserActiveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        is_active = payload.validated_data["is_active"]
        if user == request.user and not is_active:
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = is_active
        user.save(update_fields=["is_active"])
        return Response(_user_row(user))


class AdminUserResetPasswordView(APIView):
    """POST /api/admin/users/<id>/reset-password/: issue a temp password."""

    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        temp_password = get_random_string(16)
        user.set_password(temp_password)
        user.save(update_fields=["password"])
        return Response({"username": user.username, "temp_password": temp_password})


class AdminPlatformSettingsView(APIView):
    """GET/PATCH /api/admin/settings/: deployment flags.

    `show_debug_ui` is reported for visibility but rejected on PATCH:
    it's the env-driven SAST_DEBUG_UI, which gates URL mounting at
    import time. A DB write couldn't take effect without a restart,
    and silently accepting it would lie to the operator.
    """

    permission_classes = [IsAdminUser]

    @staticmethod
    def _payload():
        return {
            "hide_local_source": PlatformSettings.get_solo().hide_local_source,
            "show_debug_ui": django_settings.SAST_DEBUG_UI,
        }

    def get(self, request):
        return Response(self._payload())

    def patch(self, request):
        if "show_debug_ui" in request.data:
            return Response(
                {"detail": "show_debug_ui is env-managed (SAST_DEBUG_UI) "
                           "and needs a server restart to change."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if "hide_local_source" in request.data:
            value = request.data["hide_local_source"]
            if not isinstance(value, bool):
                return Response(
                    {"detail": "hide_local_source must be a boolean."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            row = PlatformSettings.get_solo()
            row.hide_local_source = value
            row.save(update_fields=["hide_local_source"])
        return Response(self._payload())


def _reset_request_row(req):
    return {
        "id": req.id,
        "identifier": req.identifier,
        "created_at": req.created_at.isoformat(),
        "handled": req.handled,
    }


class AdminResetRequestsView(APIView):
    """GET /api/admin/reset-requests/: pending requests first (model
    ordering), capped at 100.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = PasswordResetRequest.objects.all()[:100]
        return Response([_reset_request_row(r) for r in rows])


class AdminResetRequestDetailView(APIView):
    """PATCH /api/admin/reset-requests/<id>/: flip a request's handled flag."""

    permission_classes = [IsAdminUser]

    def patch(self, request, request_id):
        try:
            req = PasswordResetRequest.objects.get(pk=request_id)
        except PasswordResetRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        raw = request.data.get("handled", True)
        req.handled = raw if isinstance(raw, bool) else str(raw).lower() in ("true", "1")
        req.save(update_fields=["handled"])
        return Response(_reset_request_row(req))
