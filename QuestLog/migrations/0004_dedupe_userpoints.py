from django.db import migrations
from django.db.models import Count

def dedupe_userpoints(apps, schema_editor):
    UserPoints = apps.get_model('QuestLog', 'UserPoints')
    
    duplicates = (
        UserPoints.objects
        .values('user_id', 'party_id')
        .annotate(row_count=Count('id'))
        .filter(row_count__gt=1)
    )

    for duplicate in duplicates:
        rows = list(
            UserPoints.objects
            .filter(
                user_id=duplicate['user_id'],
                party_id=duplicate['party_id'],
            )
            .order_by("id")
        )

        keeper = rows[0]
        keeper.points = sum(row.points for row in rows)
        keeper.save(update_fields=["points"])

        for extra in rows[1:]:
            extra.delete()

class Migration(migrations.Migration):
    
    dependencies = [
        ('QuestLog', '0003_partysecret_reward_party_task_userpoints'),
    ]

    operations = [
        migrations.RunPython(dedupe_userpoints, migrations.RunPython.noop),
    ]