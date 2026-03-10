from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from .utilities import validate_upload, secure_upload_path_avatars, secure_upload_path_proofs
import hashlib
import uuid


class User(AbstractUser):
    display_name = models.CharField(max_length=100,blank=True,null=True)

class Reward(models.Model):
    class_attributes = models.CharField(default="To be determined",max_length=100)



class PartySecret(models.Model):
    name = models.CharField(max_length=50)
    secret_hash = models.CharField(max_length=64, editable=True) #We want to change the password 
    def set_secret(self, raw_secret):
        self.secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

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
    avatar = models.FileField(upload_to=secure_upload_path_avatars,blank=True,null=True,validators=[validate_upload]) 



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
    proofs = models.FileField(upload_to=secure_upload_path_proofs,blank=True,null=True,validators=[validate_upload]) #pictures of completed task
    affiliation = models.ForeignKey(Party, on_delete=models.CASCADE)
    recurring = models.IntegerField(default=0)# 0 means doesnt recur, nonzero is number of days
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
