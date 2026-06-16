from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from scans import views


# Project-wide error handlers. Active when DEBUG=False; Django renders
# its own diagnostic pages under DEBUG=True regardless.
handler404 = "scans.views.handler_404"


def root_redirect(request):
    """Send the user to the Vue SPA. The /app/ route is the primary UI.

    Production (DEBUG=False) only ever serves /app/ for end users.
    Development (DEBUG=True) still has /debug/ as a fallback in case
    the SPA is mid-build; users navigate there manually.
    """
    return redirect('/app/')


def app_placeholder(request):
    """Stand-in for the Vue SPA until it's wired into Django's URLs.

    Once Vite builds the production bundle, this view gets replaced
    with one that serves `frontend/dist/index.html`. For now we just
    redirect to the templated fallback so login lands somewhere real.
    """
    return redirect('/debug/projects/')


urlpatterns = [
    path('', root_redirect),
    path('admin/', admin.site.urls),
    path('accounts/', include('users.urls')),
    path('api/', include('scans.api.urls')),
    path('app/', app_placeholder),
    path('crash/', views.crash),  # forces a 500, kept for testing error pages
]

# Templated UI, debug fallback only. Production sets
# SAST_DEBUG_UI=False in .env to hide these. The Vue SPA at /app/
# is the real frontend; these routes exist so an unbuilt or broken
# SPA doesn't strand the developer.
if settings.SAST_DEBUG_UI:
    urlpatterns += [
        path('debug/', include('scans.urls')),
    ]