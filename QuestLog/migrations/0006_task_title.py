from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("QuestLog", "0005_userpoints_unique_user_points_per_party"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="title",
            field=models.CharField(default="", max_length=30),
            preserve_default=False,
        ),
    ]
