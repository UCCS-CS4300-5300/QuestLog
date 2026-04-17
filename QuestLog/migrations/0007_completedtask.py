import QuestLog.utilities
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("QuestLog", "0006_task_title"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompletedTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=30)),
                ("description", models.CharField(max_length=200)),
                ("point_value", models.PositiveIntegerField(default=0)),
                (
                    "proof",
                    models.FileField(
                        upload_to=QuestLog.utilities.secure_upload_path_proofs,
                        validators=[
                            QuestLog.utilities.validate_upload,
                            QuestLog.utilities.scan_for_malicious_code,
                            QuestLog.utilities.validate_image_file,
                        ],
                    ),
                ),
                ("completed_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
