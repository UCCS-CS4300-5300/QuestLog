from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models


def profile_picture_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"profile_pictures/{uuid4().hex}{extension}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=150)
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_to,
        blank=True,
    )

    def __str__(self):
        return self.display_name or self.user.get_username()


def get_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"display_name": user.get_username()},
    )
    return profile


def save_user_profile(user, display_name=None, profile_picture=None):
    profile = get_user_profile(user)

    if display_name:
        profile.display_name = display_name
    elif not profile.display_name:
        profile.display_name = user.get_username()

    if profile_picture is not None:
        profile.profile_picture = profile_picture

    profile.save()
    return profile


def get_user_display_name(user):
    return get_user_profile(user).display_name or user.get_username()
