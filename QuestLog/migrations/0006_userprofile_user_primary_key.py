import django.db.models.deletion
from django.db import migrations, models


def _identifier_converter(connection):
    converter = getattr(connection.introspection, "identifier_converter", None)
    if converter is None:
        return lambda value: value.lower()
    return converter


def assert_userprofile_schema_compatible(apps, schema_editor):
    connection = schema_editor.connection
    UserProfile = apps.get_model("QuestLog", "UserProfile")
    configured_table_name = UserProfile._meta.db_table
    normalize = _identifier_converter(connection)

    with connection.cursor() as cursor:
        table_names = {
            normalize(table_name): table_name
            for table_name in connection.introspection.table_names(cursor)
        }
        table_name = table_names.get(normalize(configured_table_name))
        if not table_name:
            raise RuntimeError(
                f"Expected table {configured_table_name!r} to exist before migrating UserProfile."
            )

        columns = {
            normalize(column.name)
            for column in connection.introspection.get_table_description(cursor, table_name)
        }
        if normalize("user_id") not in columns:
            raise RuntimeError(
                f"Table {table_name!r} is missing the required user_id column for UserProfile."
            )

        constraints = connection.introspection.get_constraints(cursor, table_name)
        user_id_is_unique = False
        for constraint in constraints.values():
            normalized_columns = [normalize(column) for column in constraint.get("columns", [])]
            if normalized_columns != [normalize("user_id")]:
                continue
            if constraint.get("primary_key") or constraint.get("unique"):
                user_id_is_unique = True
                break

        if not user_id_is_unique:
            raise RuntimeError(
                f"Table {table_name!r} must keep user_id uniquely constrained before "
                "QuestLog can treat it as the UserProfile primary key."
            )


def raise_irreversible(*args, **kwargs):
    raise migrations.IrreversibleError(
        "QuestLog migration 0006 intentionally only updates migration state. "
        "Reversing it would risk desynchronizing Django's state from existing "
        "production databases that already use user_id as the profile identifier."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("QuestLog", "0005_userpoints_unique_user_points_per_party"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    assert_userprofile_schema_compatible,
                    raise_irreversible,
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="userprofile",
                    name="id",
                ),
                migrations.AlterField(
                    model_name="userprofile",
                    name="user",
                    field=models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="profile",
                        serialize=False,
                        to="auth.user",
                    ),
                ),
            ],
        ),
    ]
