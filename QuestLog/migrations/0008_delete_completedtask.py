from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("QuestLog", "0007_completedtask"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CompletedTask",
        ),
    ]
