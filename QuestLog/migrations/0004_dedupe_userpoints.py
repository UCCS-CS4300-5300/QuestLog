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

            reward_ids = {row.rewards_id for row in rows}
            reward_ids.discard(None)

            if len(reward_ids) > 1:
                raise ValueError(
                    f"Too many conflciting rewards found for user_id={duplicate['user_id']} "
                    f"and party_id={duplicate['party_id']}. Clean up the data before running this migration."
                )
            
            avatar_to_keep = keeper.avatar
            if not avatar_to_keep:
                for row in rows[1:]:
                    if row.avatar:
                        avatar_to_keep = row.avatar
                        break
            reward_to_keep = keeper.rewards_id
            if reward_to_keep is None and len(reward_ids) == 1:
                reward_to_keep = next(iter(reward_ids))

            keeper.points = total_points
            keeper.avatar = avatar_to_keep
            keeper.rewards_id = reward_to_keep

            for extra in rows[1:]:
                extra.delete()

            keeper.save()

class Migration(migrations.Migration):
    
    dependencies = [
        ('QuestLog', '0003_partysecret_reward_party_task_userpoints'),
    ]

    operations = [
        migrations.RunPython(dedupe_userpoints, migrations.RunPython.noop),
    ]