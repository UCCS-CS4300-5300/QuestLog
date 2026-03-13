from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=150)
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
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


def get_user_display_name(user):
    return get_user_profile(user).display_name or user.get_username()
