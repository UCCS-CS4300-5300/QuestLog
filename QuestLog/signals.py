from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import save_user_profile


User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="questlog_create_user_profile")
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile_data = getattr(instance, "_questlog_profile_data", {})
        save_user_profile(
            instance,
            display_name=profile_data.get("display_name"),
            profile_picture=profile_data.get("profile_picture"),
        )
        if hasattr(instance, "_questlog_profile_data"):
            delattr(instance, "_questlog_profile_data")
