from django.core.management.base import BaseCommand, CommandError
from scans.models import Project
from scans.services.scan_service import ScanService

class Command(BaseCommand):
    help = "Run a scan for a project by ID"

    def add_arguments(self, parser):
        parser.add_argument(
            "project_id",
            type=str,
            help="Project ID (UUID or integer)"
        )
        parser.add_argument(
            "--tool",
            type=str,
            choices=["semgrep", "sonarqube"],
            default="semgrep",
            help="Select the scanning tool"
        )

    def handle(self, *args, **options):
        project_id = options["project_id"]
        tool = options["tool"]

        # Get project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project {project_id} not found")

        self.stdout.write(f"Running {tool} scan on project: {project.name}")

        service = ScanService()
        result = service.run_scan(project, tool=tool)

        if not result.get("success"):
            self.stdout.write(self.style.ERROR(f"Scan FAILED: {result['error']}"))
            return

        # Print result summary
        self.stdout.write(self.style.SUCCESS("Scan SUCCESS"))
        self.stdout.write(f"Scan ID: {result['scan_id']}")
        self.stdout.write(f"Duration: {result['duration_seconds']}s")
        self.stdout.write(f"Total findings: {result['total_findings']}")

        self.stdout.write("By Severity:")
        for severity, count in result["by_severity"].items():
            self.stdout.write(f"  {severity}: {count}")

        return
