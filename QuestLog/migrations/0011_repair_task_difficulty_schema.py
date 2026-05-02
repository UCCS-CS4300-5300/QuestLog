"""Repair task difficulty schema drift in deployed databases."""

# pylint: disable=invalid-name,unused-argument

from django.db import migrations


def table_names(schema_editor):
    """Return the database's current table names."""

    return schema_editor.connection.introspection.table_names()


def column_names(schema_editor, table_name):
    """Return the database's current column names for a table."""

    with schema_editor.connection.cursor() as cursor:
        return {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor,
                table_name,
            )
        }


def add_missing_task_field(schema_editor, task_model, field_name):
    """Add a task field only when the backing column is absent."""

    field = task_model._meta.get_field(field_name)
    if field.column in column_names(schema_editor, task_model._meta.db_table):
        return

    schema_editor.add_field(task_model, field)


def repair_task_difficulty_schema(apps, schema_editor):
    """Repair missing columns/tables from the task difficulty migration."""

    task_model = apps.get_model("QuestLog", "Task")
    vote_model = apps.get_model("QuestLog", "TaskDifficultyVote")
    existing_tables = table_names(schema_editor)

    if task_model._meta.db_table not in existing_tables:
        return

    add_missing_task_field(schema_editor, task_model, "name")
    add_missing_task_field(schema_editor, task_model, "difficulty_rating")

    if vote_model._meta.db_table not in table_names(schema_editor):
        schema_editor.create_model(vote_model)


class Migration(migrations.Migration):
    """Database-only repair for Render schema drift."""

    dependencies = [
        ("QuestLog", "0010_unique_default_reward"),
    ]

    operations = [
        migrations.RunPython(repair_task_difficulty_schema, migrations.RunPython.noop),
    ]
