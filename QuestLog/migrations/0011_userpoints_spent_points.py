# Generated to keep UserPoints compatible with deployed databases.

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
        return


class Migration(migrations.Migration):

    dependencies = [
        ("QuestLog", "0010_userprofile_flair_fields"),
    ]

    operations = [
        AddFieldIfMissing(
            model_name="userpoints",
            name="spent_points",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
