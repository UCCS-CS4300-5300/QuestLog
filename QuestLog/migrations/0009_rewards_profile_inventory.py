"""Add reward shop inventory and profile customization fields."""

# pylint: disable=invalid-name,protected-access,unused-argument

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

MARKER_TABLE = "QuestLog_0009_schema_markers"


def marker_table_exists(schema_editor):
    """Return whether the migration marker table exists."""

    return MARKER_TABLE in schema_editor.connection.introspection.table_names()


def ensure_marker_table(schema_editor):
    """Create the migration marker table if needed."""

    schema_editor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_editor.quote_name(MARKER_TABLE)} (
            operation_key varchar(255) NOT NULL PRIMARY KEY
        )
        """
    )


def add_marker(schema_editor, operation_key):
    """Record that this migration created schema."""

    ensure_marker_table(schema_editor)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {schema_editor.quote_name(MARKER_TABLE)} (operation_key)
            VALUES (%s)
            """,
            [operation_key],
        )


def has_marker(schema_editor, operation_key):
    """Return whether this migration created schema for an operation."""

    if not marker_table_exists(schema_editor):
        return False

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT 1
            FROM {schema_editor.quote_name(MARKER_TABLE)}
            WHERE operation_key = %s
            """,
            [operation_key],
        )
        return cursor.fetchone() is not None


def remove_marker(schema_editor, operation_key):
    """Delete an operation marker after rollback."""

    if not marker_table_exists(schema_editor):
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            DELETE FROM {schema_editor.quote_name(MARKER_TABLE)}
            WHERE operation_key = %s
            """,
            [operation_key],
        )
        cursor.execute(
            f"SELECT 1 FROM {schema_editor.quote_name(MARKER_TABLE)} LIMIT 1"
        )
        marker_remains = cursor.fetchone() is not None

    if not marker_remains:
        schema_editor.execute(f"DROP TABLE {schema_editor.quote_name(MARKER_TABLE)}")


class AddFieldIfMissing(migrations.AddField):
    """Add a field only when its database column is missing."""

    def marker_key(self, app_label, table_name, column_name):
        """Return the marker key for this field operation."""

        return f"{app_label}.add_field.{table_name}.{column_name}"

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        to_model = to_state.apps.get_model(app_label, self.model_name)
        field = to_model._meta.get_field(self.name)
        table_name = to_model._meta.db_table

        with schema_editor.connection.cursor() as cursor:
            columns = {
                column.name
                for column in schema_editor.connection.introspection.get_table_description(
                    cursor,
                    table_name,
                )
            }

        if field.column in columns:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)
        add_marker(
            schema_editor,
            self.marker_key(app_label, table_name, field.column),
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        """Remove only columns created by this migration."""

        from_model = from_state.apps.get_model(app_label, self.model_name)
        field = from_model._meta.get_field(self.name)
        operation_key = self.marker_key(app_label, from_model._meta.db_table, field.column)

        if not has_marker(schema_editor, operation_key):
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)
        remove_marker(schema_editor, operation_key)


class CreateModelIfMissing(migrations.CreateModel):
    """Create a table only when it is missing."""

    def marker_key(self, app_label, table_name):
        """Return the marker key for this table operation."""

        return f"{app_label}.create_model.{table_name}"

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.name)
        table_names = schema_editor.connection.introspection.table_names()

        if model._meta.db_table in table_names:
            return

        super().database_forwards(app_label, schema_editor, from_state, to_state)
        add_marker(
            schema_editor,
            self.marker_key(app_label, model._meta.db_table),
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        """Remove only tables created by this migration."""

        model = from_state.apps.get_model(app_label, self.name)
        operation_key = self.marker_key(app_label, model._meta.db_table)

        if not has_marker(schema_editor, operation_key):
            return

        super().database_backwards(app_label, schema_editor, from_state, to_state)
        remove_marker(schema_editor, operation_key)


class Migration(migrations.Migration):
    """Migration for reward purchases and profile flair."""

    dependencies = [
        ("QuestLog", "0008_alter_task_difficulty_rating_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
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
        AddFieldIfMissing(
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
        AddFieldIfMissing(
            model_name="reward",
            name="name",
            field=models.CharField(blank=True, max_length=120),
        ),
        AddFieldIfMissing(
            model_name="reward",
            name="description",
            field=models.TextField(blank=True, max_length=300),
        ),
        AddFieldIfMissing(
            model_name="reward",
            name="point_cost",
            field=models.PositiveIntegerField(default=0),
        ),
        AddFieldIfMissing(
            model_name="reward",
            name="reward_type",
            field=models.CharField(
                choices=[
                    ("custom", "Custom reward"),
                    ("profile_title", "Profile title"),
                    ("calling_card", "Calling card"),
                ],
                default="custom",
                max_length=20,
            ),
        ),
        AddFieldIfMissing(
            model_name="reward",
            name="profile_value",
            field=models.CharField(blank=True, max_length=120),
        ),
        AddFieldIfMissing(
            model_name="reward",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        AddFieldIfMissing(
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
        AddFieldIfMissing(
            model_name="reward",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
        AddFieldIfMissing(
            model_name="userpoints",
            name="spent_points",
            field=models.PositiveIntegerField(default=0),
        ),
        CreateModelIfMissing(
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
