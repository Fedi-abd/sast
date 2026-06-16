from django.urls import path
from rest_framework.routers import DefaultRouter

from . import admin_views, views

router = DefaultRouter()
router.register("projects", views.ProjectViewSet, basename="project")
router.register("scans", views.ScanViewSet, basename="scan")

urlpatterns = [
    path("me/", views.MeView.as_view(), name="me"),
    path("config/", views.ConfigView.as_view(), name="config"),
    path("health/", views.HealthView.as_view(), name="health"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("findings/", views.CrossProjectFindingsView.as_view(), name="findings"),
    path(
        "findings/<uuid:finding_id>/solve/",
        views.SolveFindingView.as_view(),
        name="finding-solve",
    ),
    path(
        "scans/<uuid:scan_id>/report.pdf",
        views.ScanReportPDFView.as_view(),
        name="scan-report",
    ),
    # Staff-only console endpoints (gated by IsAdminUser, not just by
    # the SPA hiding the nav item).
    path("admin/sonarqube/", admin_views.AdminSonarConfigView.as_view(), name="admin-sonarqube"),
    path("admin/sonarqube/test/", admin_views.AdminSonarTestView.as_view(), name="admin-sonarqube-test"),
    path("admin/limits/", admin_views.AdminLimitsView.as_view(), name="admin-limits"),
    path("admin/usage/", admin_views.AdminUsageView.as_view(), name="admin-usage"),
    path("admin/users/", admin_views.AdminUsersView.as_view(), name="admin-users"),
    path("admin/users/<int:user_id>/", admin_views.AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/users/<int:user_id>/reset-password/", admin_views.AdminUserResetPasswordView.as_view(), name="admin-user-reset-password"),
    path("admin/settings/", admin_views.AdminPlatformSettingsView.as_view(), name="admin-settings"),
    path("admin/reset-requests/", admin_views.AdminResetRequestsView.as_view(), name="admin-reset-requests"),
    path("admin/reset-requests/<int:request_id>/", admin_views.AdminResetRequestDetailView.as_view(), name="admin-reset-request-detail"),
    *router.urls,
]
