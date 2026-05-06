from django.contrib import admin
from .models import Project, Scan, Finding

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'language', 'created_at', 'owner']
    search_fields = ['name']
    list_filter = ['language', 'created_at']

@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ['project', 'tool', 'status', 'started_at', 'duration_seconds']
    list_filter = ['status', 'tool']
    search_fields = ['project__name']

@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = ['rule_id', 'severity', 'file_path', 'line_number', 'owasp_category']
    list_filter = ['severity', 'owasp_category', 'tool']
    search_fields = ['rule_id', 'message']
