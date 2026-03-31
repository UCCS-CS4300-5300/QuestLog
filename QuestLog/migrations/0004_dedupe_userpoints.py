from django.db import migrations, transaction
from django.db.models import Count

def dedupe_userpoints(apps, schema_editor):
    UserPoints = apps.get_model('QuestLog', 'UserPoints')
    
    with transaction.atomic():
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
            total_points = sum(row.points for row in rows)
            keeper.points = total_points

            for extra in rows[1:]:
                if not keeper.avatar and extra.avatar:
                    keeper.avatar = extra.avatar
                
                if keeper.rewards_id is None and extra.rewards_id is not None:
                    keeper.rewards_id = extra.rewards_id

            keeper.save()

            for extra in rows[1:]:
                extra.delete()

class Migration(migrations.Migration):
    
    dependencies = [
        ('QuestLog', '0003_partysecret_reward_party_task_userpoints'),
    ]

    operations = [
        migrations.RunPython(dedupe_userpoints, migrations.RunPython.noop),
    ]