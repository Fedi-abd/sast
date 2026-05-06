# scans/urls.py
from django.urls import path
from . import views

app_name = "scans"

urlpatterns = [
    # Projects CRUD…
    path("projects/", views.ProjectListView.as_view(), name="project_list"),
    path("projects/create/", views.ProjectCreateView.as_view(), name="project_create"),
    path("projects/<uuid:pk>/edit/", views.ProjectUpdateView.as_view(), name="project_edit"),
    path("projects/<uuid:pk>/delete/", views.ProjectDeleteView.as_view(), name="project_delete"),
    path("projects/<uuid:pk>/", views.ProjectDetailView.as_view(), name="project_detail"),

    # US12: Trigger Scan
    path("projects/<uuid:project_id>/scan/", views.trigger_scan, name="trigger_scan"),

    # US12: Scan detail
    path("scans/<uuid:pk>/", views.ScanDetailView.as_view(), name="scan_detail"),
]