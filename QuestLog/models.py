from django.db import models

# Create your models here.
# /////////////Structures///////////////////

#Darin
class User(models.Model):
    field="value"
#Darin    
class UserPoints(models.Model):
    field="value"

#Vlad
class Party(models.Model):
    guid = models.BigIntegerField()# uniq
    party_name = models.CharField(max_length=200)
    members = models.ManyToManyField(User, related_name="parties")
    # group_tasks = models.ForeignKey(Group_task)  #REMOVED
    # task_pool = models.ForeignKey(Task)       #Reverse defined in Task.affiliation                                 
    # leaderboard = models.OneToOneField(Leaderboard)   #REMOVED
    # requests = models.ForeignKey(User)    #REMOVED
    creator = models.ForeignKey(User, on_delete=models.CASCADE)  #Admin
    secret = models.CharField(max_length=200) #probably wrong type

#Vlad
class Task(models.Model):
    class Status(models.IntegerChoices):
        NOT_STARTED = 0, "Not started"
        IN_PROGRESS = 1, "In progress/Claimed"
        COMPLETED = 2, "Completed"


    owner = models.ForeignKey(User,  on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    point_value = models.PositiveIntegerField(default=0)
    proofs = models.FileField(upload_to='proofs/') #pictures of completed task
    affiliation = models.ForeignKey(Party, on_delete=models.CASCADE)
    recurring = models.IntegerField(default=0)# 0 means doesnt recur, nonzero is number of days
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now_add=True)
