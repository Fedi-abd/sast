# Revision 1 (Sprint 1): constrain Scan.tool to the supported tool set.
# The initial migration created tool as CharField(max_length=50) with no choices,
# which allowed invalid scan rows like tool="abc". The model now declares
# choices=TOOL_CHOICES with max_length=20; this migration brings the schema in
# line with the model.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scans', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scan',
            name='tool',
            field=models.CharField(
                choices=[('semgrep', 'Semgrep'), ('sonarqube', 'SonarQube')],
                max_length=20,
            ),
        ),
    ]
