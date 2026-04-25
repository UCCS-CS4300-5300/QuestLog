# Generated manually for the task completion and rewards flow.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("QuestLog", "0007_task_difficulty_rating_task_name_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="reward",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reward",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_rewards",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="reward",
            name="description",
            field=models.TextField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="reward",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="reward",
            name="name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="reward",
            name="party",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reward_catalog",
                to="QuestLog.party",
            ),
        ),
        migrations.AddField(
            model_name="reward",
            name="point_cost",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="task",
            name="completed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="completed_tasks",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="userpoints",
            name="spent_points",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="RewardPurchase",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("points_spent", models.PositiveIntegerField()),
                ("purchased_at", models.DateTimeField(auto_now_add=True)),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reward_purchases",
                        to="QuestLog.party",
                    ),
                ),
                (
                    "reward",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchases",
                        to="QuestLog.reward",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reward_purchases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-purchased_at"],
            },
        ),
    ]
