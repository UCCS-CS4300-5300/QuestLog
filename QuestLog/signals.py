from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import get_user_profile


User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="questlog_create_user_profile")
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        get_user_profile(instance)
