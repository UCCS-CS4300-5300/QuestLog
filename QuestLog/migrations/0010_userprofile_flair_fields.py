# Generated to keep UserProfile compatible with deployed databases.

from django.db import migrations, models


class AddFieldIfMissing(migrations.AddField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        to_model = to_state.apps.get_model(app_label, self.model_name)
        field = to_model._meta.get_field(self.name)

        with schema_editor.connection.cursor() as cursor:
            existing_columns = {
                column.name
                for column in schema_editor.connection.introspection.get_table_description(
                    cursor,
                    to_model._meta.db_table,
                )
            }

        if field.column in existing_columns:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # The target deployment already has these columns in some databases.
        # Avoid deleting pre-existing data if this repair migration is rolled back.
        return


class Migration(migrations.Migration):

    dependencies = [
        ("QuestLog", "0009_task_bounty"),
    ]

    operations = [
        AddFieldIfMissing(
            model_name="userprofile",
            name="profile_title",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        AddFieldIfMissing(
            model_name="userprofile",
            name="calling_card",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        AddFieldIfMissing(
            model_name="userprofile",
            name="selected_badges",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
