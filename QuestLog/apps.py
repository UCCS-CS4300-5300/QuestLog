from django.apps import AppConfig


class QuestlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "QuestLog"

    def ready(self):
        from . import signals  # noqa: F401
