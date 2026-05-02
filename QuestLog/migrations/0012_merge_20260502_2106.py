"""Merge reward-profile and task-bounty migration branches."""

# pylint: disable=invalid-name,missing-class-docstring

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('QuestLog', '0011_repair_task_difficulty_schema'),
        ('QuestLog', '0011_userpoints_spent_points'),
    ]

    operations = [
    ]
