from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    display_name = models.CharField(max_length=150)
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
    )

    REQUIRED_FIELDS = ["display_name"]

    def __str__(self):
        return self.display_name or self.username
