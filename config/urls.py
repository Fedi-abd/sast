from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from scans import views


def root_redirect(request):
    return redirect('/projects/')


urlpatterns = [
    path('', root_redirect),
    path('admin/', admin.site.urls),
    path('accounts/', include('users.urls')),
    path('crash/', views.crash),  # forces a 500 — kept for testing error pages
    path('', include('scans.urls')),
]