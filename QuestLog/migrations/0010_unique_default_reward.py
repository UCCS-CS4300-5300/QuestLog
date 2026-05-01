"""Make the default reward placeholder unique."""

# pylint: disable=duplicate-code,invalid-name

from django.db import migrations, models


def dedupe_default_rewards(apps, schema_editor):
    """Collapse duplicate default reward placeholders before adding the constraint."""

    db_alias = schema_editor.connection.alias
    reward_model = apps.get_model("QuestLog", "Reward")
    user_points_model = apps.get_model("QuestLog", "UserPoints")
    reward_purchase_model = apps.get_model("QuestLog", "RewardPurchase")

    default_rewards = list(
        reward_model.objects.using(db_alias)
        .filter(class_attributes="Default Reward", party__isnull=True)
        .order_by("id")
    )

    if not default_rewards:
        return

    canonical_reward = default_rewards[0]

    if not canonical_reward.name:
        canonical_reward.name = "Default Reward"
        canonical_reward.save(update_fields=["name"])

    duplicate_ids = [reward.pk for reward in default_rewards[1:]]
    if not duplicate_ids:
        return

    user_points_model.objects.using(db_alias).filter(
        rewards_id__in=duplicate_ids,
    ).update(rewards_id=canonical_reward.pk)
    reward_purchase_model.objects.using(db_alias).filter(
        reward_id__in=duplicate_ids,
    ).update(reward_id=canonical_reward.pk)
    reward_model.objects.using(db_alias).filter(pk__in=duplicate_ids).delete()


class Migration(migrations.Migration):
    """Migration for default reward uniqueness."""

    dependencies = [
        ("QuestLog", "0009_rewards_profile_inventory"),
    ]

    operations = [
        migrations.RunPython(dedupe_default_rewards, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="reward",
            constraint=models.UniqueConstraint(
                fields=["class_attributes"],
                condition=models.Q(
                    class_attributes="Default Reward",
                    party__isnull=True,
                ),
                name="unique_default_reward_placeholder",
            ),
        ),
    ]
