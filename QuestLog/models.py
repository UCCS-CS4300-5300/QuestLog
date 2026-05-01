from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
import uuid
from QuestLog.utilities import scan_for_malicious_code, secure_upload_path_avatars, secure_upload_path_proofs, validate_image_file, validate_upload

from collections import defaultdict

MAX_DISPLAY_BADGES = 3
BADGE_CATALOG = [
    {
        "code": "first_quest",
        "name": "First Quest",
        "description": "Complete your first quest.",
        "task_goal": 1,
    },
    {
        "code": "helping_hand",
        "name": "Helping Hand",
        "description": "Complete 5 quests.",
        "task_goal": 5,
    },
    {
        "code": "quest_streak",
        "name": "Quest Streak",
        "description": "Complete 10 quests.",
        "task_goal": 10,
    },
    {
        "code": "guild_legend",
        "name": "Guild Legend",
        "description": "Complete 25 quests.",
        "task_goal": 25,
    },
]

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
    profile_title = models.CharField(max_length=80, blank=True, default="")
    calling_card = models.CharField(max_length=120, blank=True, default="")
    selected_badges = models.JSONField(blank=True, default=list)

    def __str__(self):
        return self.display_name or self.user.get_username()

    @property
    def display_badges(self):
        return get_selected_badges(self)


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


def get_completed_task_count(user):
    return Task.objects.filter(owner=user, status=Task.Status.COMPLETED).count()


def get_earned_badges(user):
    completed_task_count = get_completed_task_count(user)
    return [
        badge
        for badge in BADGE_CATALOG
        if completed_task_count >= badge["task_goal"]
    ]


def get_selected_badges(profile, earned_badges=None):
    earned_badges = earned_badges if earned_badges is not None else get_earned_badges(profile.user)
    earned_by_code = {badge["code"]: badge for badge in earned_badges}
    selected_codes = profile.selected_badges if isinstance(profile.selected_badges, list) else []
    selected_badges = []

    for code in selected_codes:
        if code in earned_by_code:
            selected_badges.append(earned_by_code[code])
        if len(selected_badges) >= MAX_DISPLAY_BADGES:
            break

    return selected_badges

#gen leaderboard
def genLeaderboard(user):
    user_parties = list(user.parties.all().order_by("party_name"))

    points_rows = (
        UserPoints.objects
        .filter(party__in=user_parties)
        .select_related("user", "party", "rewards", "user__profile")
        .order_by("party__party_name", "-points", "user__username")
    )

    standings_by_party_id = defaultdict(list)
    for row in points_rows:
        standings_by_party_id[row.party_id].append(row)

    party_leaderboards = []
    for party in user_parties:
        party_leaderboards.append({
            "party": party,
            "standings": standings_by_party_id[party.id],
        })
    return party_leaderboards

#get parties
def getParties(user):
    user_parties = (
        user.parties.all()
        .order_by("party_name")
    )
    return user_parties

#get party details
def getPartyDetails(user, guid):
    try:
        party = Party.objects.get(guid=guid)
    except Party.DoesNotExist:
        return None
    
    if party.members.filter(pk=user.pk).exists():
        #return details
        return party
    else:
        #return error
        return None

def getPartyTasks(party):
    return (
        Task.objects.filter(affiliation=party)
        .select_related("owner")
        .prefetch_related("difficulty_votes__voter")
        .order_by("status", "-created_at")
    )

def getPartyMembers(party):
    return party.members.all().order_by("username")


def getPendingPartyInvitations(user):
    return (
    PartyInvitation.objects
    .filter(invited_user=user, status=PartyInvitation.Status.PENDING)
    .select_related("party", "invited_by")
    .order_by("-created_at")
    )

class Reward(models.Model):
    class RewardType(models.TextChoices):
        CUSTOM = "custom", "Custom reward"
        PROFILE_TITLE = "profile_title", "Profile title"
        CALLING_CARD = "calling_card", "Calling card"

    class_attributes = models.CharField(default="To be determined",max_length=100)
    party = models.ForeignKey(
        "Party",
        on_delete=models.CASCADE,
        related_name="reward_catalog",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120, blank=True)
    description = models.TextField(max_length=300, blank=True)
    point_cost = models.PositiveIntegerField(default=0)
    reward_type = models.CharField(
        max_length=20,
        choices=RewardType.choices,
        default=RewardType.CUSTOM,
    )
    profile_value = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_rewards",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    @property
    def label(self):
        return self.name or self.class_attributes

    @property
    def profile_reward_value(self):
        return (self.profile_value or self.label).strip()

    @property
    def updates_profile(self):
        return self.reward_type in {
            self.RewardType.PROFILE_TITLE,
            self.RewardType.CALLING_CARD,
        }

    def apply_to_profile(self, user):
        if not self.updates_profile:
            return False

        profile = get_user_profile(user)
        value = self.profile_reward_value

        if self.reward_type == self.RewardType.PROFILE_TITLE:
            profile.profile_title = value
            profile.save(update_fields=["profile_title"])
            return True

        if self.reward_type == self.RewardType.CALLING_CARD:
            profile.calling_card = value
            profile.save(update_fields=["calling_card"])
            return True

        return False

    def __str__(self):
        return self.label


def get_default_reward():
    reward = (
        Reward.objects
        .filter(class_attributes="Default Reward", party__isnull=True)
        .order_by("id")
        .first()
    )
    if reward is None:
        reward = Reward.objects.create(
            class_attributes="Default Reward",
            party=None,
            name="Default Reward",
            description="Tracks party membership before a reward is purchased.",
            point_cost=0,
        )
    elif not reward.name:
        reward.name = "Default Reward"
        reward.save(update_fields=["name"])

    return reward

class PartySecret(models.Model):
    _secret_hash = models.CharField(max_length=128, editable=False)

    def set_secret(self, raw_secret):
        self._secret_hash = make_password(raw_secret)
        self.save(update_fields=["_secret_hash"])

    def check_secret(self,raw_secret):
        return check_password(raw_secret,self._secret_hash)


class Party(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    party_name = models.CharField(max_length=200)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="parties")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  #Admin
    secret = models.OneToOneField(PartySecret,on_delete=models.PROTECT,null=True,blank=True)
    # task_pool = models.ForeignKey(Task)       #Reverse defined in Task.affiliation

    def __str__(self):
        return self.party_name

class PartyInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="invitations")
    invited_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="party_invitations",)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_party_invitations",)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["party", "invited_user"], name="unique_party_invitation_per_user_per_party")
        ]

    def __str__(self):
        return f"{self.invited_user.username} -> {self.party.party_name} ({self.status})"   


class UserPoints(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)
    spent_points = models.PositiveIntegerField(default=0)
    rewards = models.ForeignKey(Reward, on_delete=models.PROTECT)
    avatar = models.FileField(upload_to=secure_upload_path_avatars,blank=True,null=True,validators=[validate_upload,scan_for_malicious_code,validate_image_file])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "party"], name="unique_user_points_per_party")
        ]
    def __str__(self):
        return f"{self.user.username} - {self.party.party_name}: {self.points}"

    @property
    def available_points(self):
        return max(self.points - self.spent_points, 0)


class RewardPurchase(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reward_purchases",
    )
    party = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name="reward_purchases",
    )
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT, related_name="purchases")
    points_spent = models.PositiveIntegerField()
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchased_at"]

    def __str__(self):
        return f"{self.user.username} bought {self.reward.label} in {self.party.party_name}"


class Task(models.Model):
    class Status(models.IntegerChoices):
        NOT_STARTED = 0, "Not started"
        IN_PROGRESS = 1, "In progress/Claimed"
        COMPLETED = 2, "Completed"


    owner = models.ForeignKey(settings.AUTH_USER_MODEL,  on_delete=models.CASCADE)
    name = models.CharField(max_length=120, default="Untitled Task")
    description = models.TextField(max_length=500)
    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    difficulty_rating = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    point_value = models.PositiveIntegerField(default=0)
    proofs = models.FileField(upload_to=secure_upload_path_proofs,blank=True,null=True,validators=[validate_upload,scan_for_malicious_code,validate_image_file]) #pictures of completed task
    affiliation = models.ForeignKey(Party, on_delete=models.CASCADE)
    recurring = models.IntegerField(default=0)# 0 means doesnt recur, nonzero is number of days
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def difficulty_vote_count(self):
        prefetched_votes = self._prefetched_objects_cache.get("difficulty_votes") if hasattr(self, "_prefetched_objects_cache") else None
        if prefetched_votes is not None:
            return len(prefetched_votes)
        return self.difficulty_votes.count()

    @property
    def weighted_difficulty(self):
        prefetched_votes = self._prefetched_objects_cache.get("difficulty_votes") if hasattr(self, "_prefetched_objects_cache") else None

        if prefetched_votes is not None:
            votes = list(prefetched_votes)
            if votes:
                return sum(vote.rating for vote in votes) / len(votes)
            return float(self.difficulty_rating)

        aggregate = self.difficulty_votes.aggregate(avg_rating=models.Avg("rating"))
        return float(aggregate["avg_rating"] or self.difficulty_rating)

    @property
    def weighted_difficulty_display(self):
        return f"{self.weighted_difficulty:.1f}"

    def get_vote_for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return None

        prefetched_votes = self._prefetched_objects_cache.get("difficulty_votes") if hasattr(self, "_prefetched_objects_cache") else None
        if prefetched_votes is not None:
            for vote in prefetched_votes:
                if vote.voter_id == user.id:
                    return vote
            return None

        return self.difficulty_votes.filter(voter=user).first()

    def sync_point_value_with_difficulty(self, save=True):
        self.point_value = round(self.weighted_difficulty * 10)
        if save:
            self.save(update_fields=["point_value"])
        return self.point_value


class TaskDifficultyVote(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="difficulty_votes")
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_difficulty_votes")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "voter"], name="unique_task_difficulty_vote_per_user")
        ]

    def __str__(self):
        return f"{self.task.name} - {self.voter.username}: {self.rating}"
