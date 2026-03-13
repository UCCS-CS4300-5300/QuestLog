from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
import uuid
from QuestLog.utilities import scan_for_malicious_code, secure_upload_path_avatars, secure_upload_path_proofs, validate_image_file, validate_upload

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



class Reward(models.Model):
    class_attributes = models.CharField(default="To be determined",max_length=100)



class PartySecret(models.Model):
    _secret_hash = models.CharField(max_length=128, editable=False) 

    def set_secret(self, raw_secret):
        self.__secret_hash = make_password(raw_secret) 

    def check_secret(self,raw_secret):
        check_password(raw_secret,self.__secret_hash)


class Party(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    party_name = models.CharField(max_length=200)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="parties")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  #Admin
    secret = models.OneToOneField(PartySecret,on_delete=models.PROTECT,null=True,blank=True) 
    # task_pool = models.ForeignKey(Task)       #Reverse defined in Task.affiliation                                 

class UserPoints(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,  on_delete=models.CASCADE)
    party = models.ForeignKey(Party,on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)
    rewards = models.ForeignKey(Reward,on_delete=models.PROTECT)
    avatar = models.FileField(upload_to=secure_upload_path_avatars,blank=True,null=True,validators=[validate_upload,scan_for_malicious_code,validate_image_file,validate_content_type]) 



class Task(models.Model):
    class Status(models.IntegerChoices):
        NOT_STARTED = 0, "Not started"
        IN_PROGRESS = 1, "In progress/Claimed"
        COMPLETED = 2, "Completed"


    owner = models.ForeignKey(settings.AUTH_USER_MODEL,  on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    point_value = models.PositiveIntegerField(default=0)
    proofs = models.FileField(upload_to=secure_upload_path_proofs,blank=True,null=True,validators=[validate_upload,scan_for_malicious_code,validate_image_file,validate_content_type]) #pictures of completed task
    affiliation = models.ForeignKey(Party, on_delete=models.CASCADE)
    recurring = models.IntegerField(default=0)# 0 means doesnt recur, nonzero is number of days
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
