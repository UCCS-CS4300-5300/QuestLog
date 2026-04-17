#!/usr/bin/env python3

## ADDS 3 TASKS TO THE VERIFICATION USER
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model

from QuestLog.models import Party, Task


def run():
    username = "verification_user"
    password = "verification_pass_123"

    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(username=username)
    if created:
        user.set_password(password)
        user.email = "verification_user@example.com"
        user.save(update_fields=["password", "email"])
    else:
        # Keep the script idempotent so it can be re-run safely.
        user.set_password(password)
        user.save(update_fields=["password"])

    party, _ = Party.objects.get_or_create(
        party_name="Verification Party",
        creator=user,
    )
    party.members.add(user)

    tasks_to_seed = [
        ("Clean floor", "Clean the floor in the living room", 10),
        ("Wash the car", "Go out and wash the car", 15),
        ("Take out trash", "Take out all kitchen trash bags", 8),
    ]

    for title, description, points in tasks_to_seed:
        Task.objects.get_or_create(
            owner=user,
            title=title,
            defaults={
                "description": description,
                "point_value": points,
                "affiliation": party,
            },
        )

    print("Seed complete.")
    print(f"Username: {username}")
    print(f"Password: {password}")
    print("Tasks created (or confirmed): 3")


if __name__ == "__main__":
    run()
