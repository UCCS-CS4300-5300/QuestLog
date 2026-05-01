"""Views and helpers for the Quest Log app."""

# pylint: disable=invalid-name,no-member,too-many-branches,too-many-lines

import json
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import escape_leading_slashes, url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from .forms import (
    CreatePartyForm,
    CreateTaskForm,
    InviteUserForm,
    QuestLogAuthenticationForm,
    QuestLogUserCreationForm,
    RewardForm,
    TaskDifficultyVoteForm,
)
from .models import (
    BADGE_CATALOG,
    MAX_DISPLAY_BADGES,
    Party,
    PartyInvitation,
    Reward,
    RewardPurchase,
    Task,
    TaskDifficultyVote,
    UserPoints,
    UserProfile,
    get_completed_task_count,
    get_default_reward,
    get_earned_badges,
    get_selected_badges,
    get_user_display_name,
    get_user_profile,
    genLeaderboard,
    getParties,
    getPartyDetails,
    getPartyMembers,
    getPartyTasks,
    getPendingPartyInvitations,
)
from .serializers import updateProfile, updateUser

User = get_user_model()


def get_or_create_user_points(user, party, for_update=False):
    """Return a user's points row for a party."""

    default_reward = get_default_reward()
    queryset = UserPoints.objects
    if for_update:
        queryset = queryset.select_for_update()

    user_points, _ = queryset.get_or_create(
        user=user,
        party=party,
        defaults={
            "points": 0,
            "rewards": default_reward,
        },
    )
    return user_points


def ensure_party_reward_catalog(party, created_by=None):
    """Seed starter rewards for a party."""

    starter_rewards = [
        {
            "name": "Pick the next group activity",
            "description": "Choose the next movie, game, or shared activity for the party.",
            "point_cost": 50,
            "reward_type": Reward.RewardType.CUSTOM,
            "profile_value": "",
        },
        {
            "name": "Small treat fund",
            "description": "Redeem points toward a low-cost treat agreed on by the party.",
            "point_cost": 100,
            "reward_type": Reward.RewardType.CUSTOM,
            "profile_value": "",
        },
        {
            "name": "Title: Quest Champion",
            "description": "Show Quest Champion under your display name.",
            "point_cost": 60,
            "reward_type": Reward.RewardType.PROFILE_TITLE,
            "profile_value": "Quest Champion",
        },
        {
            "name": "Calling Card: Legendary Helper",
            "description": "Add Legendary Helper to your profile card.",
            "point_cost": 80,
            "reward_type": Reward.RewardType.CALLING_CARD,
            "profile_value": "Legendary Helper",
        },
    ]

    for reward_data in starter_rewards:
        Reward.objects.get_or_create(
            party=party,
            name=reward_data["name"],
            defaults={
                "class_attributes": reward_data["name"],
                "description": reward_data["description"],
                "point_cost": reward_data["point_cost"],
                "reward_type": reward_data["reward_type"],
                "profile_value": reward_data["profile_value"],
                "created_by": created_by,
            },
        )


def get_profile_reward_values(user, reward_type):
    """Return redeemed profile values for a reward type."""

    purchases = (
        RewardPurchase.objects
        .filter(user=user, reward__reward_type=reward_type)
        .select_related("reward")
        .order_by("purchased_at")
    )
    values = []
    seen = set()

    for purchase in purchases:
        value = purchase.reward.profile_reward_value
        if value and value not in seen:
            values.append(value)
            seen.add(value)

    return values


def get_profile_customization_context(user, user_profile=None):
    """Return profile customization options for templates."""

    user_profile = user_profile or get_user_profile(user)
    title_options = get_profile_reward_values(user, Reward.RewardType.PROFILE_TITLE)
    calling_card_options = get_profile_reward_values(user, Reward.RewardType.CALLING_CARD)

    if user_profile.profile_title and user_profile.profile_title not in title_options:
        title_options.insert(0, user_profile.profile_title)
    if user_profile.calling_card and user_profile.calling_card not in calling_card_options:
        calling_card_options.insert(0, user_profile.calling_card)

    earned_badges = get_earned_badges(user)
    selected_badges = get_selected_badges(user_profile, earned_badges)
    earned_badge_codes = {badge["code"] for badge in earned_badges}
    locked_badges = [
        badge
        for badge in BADGE_CATALOG
        if badge["code"] not in earned_badge_codes
    ]

    return {
        "profile": user_profile,
        "title_options": title_options,
        "calling_card_options": calling_card_options,
        "badge_catalog": BADGE_CATALOG,
        "earned_badges": earned_badges,
        "locked_badges": locked_badges,
        "selected_badges": selected_badges,
        "selected_badge_codes": [badge["code"] for badge in selected_badges],
        "max_display_badges": MAX_DISPLAY_BADGES,
        "completed_task_count": get_completed_task_count(user),
    }


def validate_profile_customizations(user, user_profile, data):
    """Validate and stage profile title, card, and badge choices."""

    errors = {}
    updated_fields = []

    if "profile_title" in data:
        selected_title = str(data.get("profile_title") or "").strip()
        title_options = get_profile_reward_values(user, Reward.RewardType.PROFILE_TITLE)
        if selected_title and selected_title not in title_options:
            errors["profile_title"] = "Choose a title you have redeemed."
        else:
            user_profile.profile_title = selected_title
            updated_fields.append("profile_title")

    if "calling_card" in data:
        selected_card = str(data.get("calling_card") or "").strip()
        calling_card_options = get_profile_reward_values(user, Reward.RewardType.CALLING_CARD)
        if selected_card and selected_card not in calling_card_options:
            errors["calling_card"] = "Choose a calling card you have redeemed."
        else:
            user_profile.calling_card = selected_card
            updated_fields.append("calling_card")

    if "selected_badges" in data:
        selected_codes = data.get("selected_badges")
        earned_codes = {badge["code"] for badge in get_earned_badges(user)}

        if not isinstance(selected_codes, list):
            errors["selected_badges"] = "Choose badges from your earned badge list."
        elif len(selected_codes) > MAX_DISPLAY_BADGES:
            errors["selected_badges"] = f"Choose up to {MAX_DISPLAY_BADGES} badges."
        else:
            clean_codes = []
            for code in selected_codes:
                if not isinstance(code, str) or code not in earned_codes:
                    errors["selected_badges"] = "Choose badges from your earned badge list."
                    break
                if code not in clean_codes:
                    clean_codes.append(code)

            if "selected_badges" not in errors:
                user_profile.selected_badges = clean_codes
                updated_fields.append("selected_badges")

    return errors, updated_fields

def get_request_hosts(request):
    """Return exact hosts accepted for this request."""

    request_host = request.get_host()
    request_hostname = urlsplit(f"//{request_host}").hostname
    exact_hosts = {request_host.lower()}
    if request_hostname:
        exact_hosts.add(request_hostname.lower())
    return exact_hosts


def get_redirect_allowed_hosts(request):
    """Return hosts allowed for redirects."""

    exact_hosts = get_request_hosts(request)
    configured_hosts = getattr(settings, "REDIRECT_ALLOWED_HOSTS", [])
    exact_hosts.update(
        host.lower()
        for host in configured_hosts
        if host and host != "*" and not host.startswith(".")
    )
    return exact_hosts


def get_safe_redirect(request):
    """Return a safe post-login redirect path."""

    redirect_to = request.POST.get("next") or request.GET.get("next")
    default_redirect = reverse("QuestLog:home")

    if not redirect_to:
        return default_redirect

    redirect_to = redirect_to.strip()
    if not redirect_to:
        return default_redirect

    try:
        redirect_parts = urlsplit(redirect_to)
    except ValueError:
        return default_redirect

    redirect_host = redirect_parts.netloc.lower()
    redirect_hostname = (redirect_parts.hostname or "").lower()
    request_hosts = get_request_hosts(request)
    is_same_host_redirect = redirect_host in request_hosts or redirect_hostname in request_hosts

    if redirect_parts.netloc and not is_same_host_redirect and redirect_parts.scheme != "https":
        return default_redirect

    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts=get_redirect_allowed_hosts(request),
        require_https=request.is_secure(),
    ):
        return escape_leading_slashes(redirect_to)

    return default_redirect

def renderPage(request, page):
    """Render a page with shared user context."""

    if not request.user.is_authenticated:
        return render(request, page)

    data = {
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
    }
    data.update(get_profile_customization_context(request.user))
    guid = request.GET.get("guid") or request.GET.get("party")
    if guid:
        data["party"] = getPartyDetails(request.user, guid)
        if data["party"] is not None:
            data["members"] = getPartyMembers(data["party"])
            data["tasks"] = getPartyTasks(data["party"])

    return render(request, page, data)

def home(request):
    """Render the home page."""

    return renderPage(request, "home.html")


def about(request):
    """Render the about page."""

    return renderPage(request, "about.html")


def tasks(request):
    """Render tasks for the selected party."""

    # If guid is missing and user has exactly one party, default to it.
    # This keeps `/tasks/` useful while preserving party selection for multi-party users.
    guid = request.GET.get("guid")
    if not guid and request.user.is_authenticated:
        user_parties = getParties(request.user)
        if user_parties.count() == 1:
            guid = str(user_parties.first().guid)

    # if still missing then show the party selection screen
    if not guid:
        return renderPage(request, "tasks.html")
    #if theres a party selected then verify membership and build task pool context
    party = getPartyDetails(request.user, guid)
    if party is None:
        messages.error(request, "Party not found or perhaps you do not have access to it")
        return redirect("QuestLog:tasks")

    available_tasks = list(
        getPartyTasks(party).filter(status=Task.Status.NOT_STARTED)
    )
    party_member_count = party.members.count()

    for task in available_tasks:
        current_vote = task.get_vote_for_user(request.user)
        task.current_user_rating = current_vote.rating if current_vote else task.difficulty_rating

    context = {
        "profile": get_user_profile(request.user),
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "party": party,
        "available_tasks": available_tasks,
        "difficulty_rating_choices": TaskDifficultyVoteForm.RATING_CHOICES,
        "party_member_count": party_member_count,
    }
    return render(request, "tasks.html", context)


def task_history(request):
    """Render completed task history."""

    if request.user.is_authenticated:
        completed_tasks = (
            Task.objects.filter(owner=request.user, status=Task.Status.COMPLETED)
            .select_related("owner", "affiliation")
            .order_by("-completed_at", "-created_at")
        )
        context = {
            "profile": get_user_profile(request.user),
            "party_leaderboards": genLeaderboard(request.user),
            "parties": getParties(request.user),
            "pending_party_invitations": getPendingPartyInvitations(request.user),
            "tasks": list(completed_tasks),
        }
        return render(request, "tasks_history.html", context)
    return render(request, "tasks_history.html", {"tasks": []})


def complete_task(request):
    """Render the task completion page."""

    if not request.user.is_authenticated:
        return redirect("QuestLog:login")

    task_id = request.GET.get("task_id")
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        messages.error(request, "Task not found.")
        return redirect("QuestLog:tasks")

    task = (
        Task.objects.filter(id=task_id, owner=request.user)
        .exclude(status=Task.Status.COMPLETED)
        .first()
    )
    if task is None:
        messages.error(request, "Task not found.")
        return redirect("QuestLog:tasks")

    return render(request, "complete_task.html", {"task": task})


def login_view(request):
    """Authenticate a user."""

    if request.user.is_authenticated:
        return redirect("QuestLog:home")

    form = QuestLogAuthenticationForm(request, data=request.POST or None)
    redirect_to = get_safe_redirect(request)

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, f"Welcome back, {get_user_display_name(form.get_user())}.")
        return redirect(redirect_to)

    return render(request, "login.html", {"form": form, "next": redirect_to})


def register(request):
    """Register a new user."""

    if request.user.is_authenticated:
        return redirect("QuestLog:home")

    form = QuestLogUserCreationForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect("QuestLog:home")

    return render(request, "register.html", {"form": form})

@login_required(login_url="QuestLog:login")
def logout_view(request):
    """Log out the current user."""

    logout(request)
    return redirect("QuestLog:home")



def normalize_media_path(path):
    """Normalize a requested media path."""

    return PurePosixPath(
        "/" + unquote(path).replace("\\", "/")
    ).as_posix().lstrip("/")


def serve_media(request, path):
    """Serve protected media files."""

    normalized_request_path = normalize_media_path(path)
    path_parts = PurePosixPath(normalized_request_path).parts
    if len(path_parts) < 2:
        raise Http404("Media file not found.")

    allowed_roots = {"profile_pictures", "proofs"}
    if path_parts[0] not in allowed_roots:
        raise Http404("Media file not found.")

    if not request.user.is_authenticated:
        raise Http404("Media file not found.")

    is_profile_picture_request = path_parts[0] == "profile_pictures"
    if is_profile_picture_request:

        is_known_profile_picture = UserProfile.objects.filter(
            profile_picture=normalized_request_path
        ).exists()
        if not is_known_profile_picture:
            raise Http404("Media file not found.")
    else:
        task_with_proof = (
            Task.objects
            .select_related("affiliation")
            .filter(proofs=normalized_request_path)
            .first()
        )
        if task_with_proof is None:
            raise Http404("Media file not found.")

        can_access_proof = task_with_proof.owner_id == request.user.id
        if not can_access_proof:
            can_access_proof = task_with_proof.affiliation.members.filter(
                pk=request.user.pk
            ).exists()
        if not can_access_proof:
            raise Http404("Media file not found.")

    media_root = Path(settings.MEDIA_ROOT).resolve()

    try:
        media_path = (media_root / normalized_request_path).resolve()
        media_path.relative_to(media_root)
    except ValueError as exc:
        raise Http404("Media file not found.") from exc

    if not media_path.is_file():
        raise Http404("Media file not found.")

    return FileResponse(media_path.open("rb"))


@login_required(login_url="QuestLog:login")
def profile(request):
    """Render or update the current user's profile."""

    if request.method == "POST":
        # We attempt to parse the json. Flag indicates success or failure
        flag = True
        try:
            data = json.loads(request.body)
        except ValueError:
            flag = False

        # keys that are allowed
        allowed_keys = {
            "display_name",
            "email",
            "profile_title",
            "calling_card",
            "selected_badges",
        }

        #flag is true if json parsed correctly and there are no unauthorized keys
        if flag and set(data).issubset(allowed_keys):
            # Deserialize user and profile separately because they are separate models.
            user_profile = get_user_profile(request.user)
            profile_data = {
                key: value
                for key, value in data.items()
                if key in {"display_name"}
            }
            user_data = {
                key: value
                for key, value in data.items()
                if key in {"email"}
            }
            profile_serializer = updateProfile(user_profile, data=profile_data, partial=True)
            user_serializer = updateUser(request.user, data=user_data, partial=True)
            customization_errors, updated_fields = validate_profile_customizations(
                request.user,
                user_profile,
                data,
            )
            if (
                profile_serializer.is_valid()
                and user_serializer.is_valid()
                and not customization_errors
            ):
                with transaction.atomic():
                    profile_serializer.save()
                    user_serializer.save()
                    if updated_fields:
                        user_profile.save(update_fields=updated_fields)

                customization_context = get_profile_customization_context(
                    request.user,
                    user_profile,
                )

                resp = Response(
                    profile_serializer.data | user_serializer.data | {
                        "profile_title": user_profile.profile_title,
                        "calling_card": user_profile.calling_card,
                        "selected_badges": customization_context["selected_badges"],
                        "selected_badge_codes": customization_context["selected_badge_codes"],
                    },
                    status=200,
                )
            else:
                resp = Response(
                    profile_serializer.errors | user_serializer.errors | customization_errors,
                    status=400,
                )
        else:
            resp = Response("Bad json or unknown keys", status=400)

        #create response
        resp.accepted_renderer = JSONRenderer()
        resp.accepted_media_type = "application/json"
        resp.renderer_context = {"request": request}

        return resp
    return renderPage(request, "profile.html")

@login_required(login_url="QuestLog:login")
def leaderboard(request):
    """Render leaderboards."""

    return renderPage(request, "leaderboard.html")


@login_required(login_url="QuestLog:login")
def rewards(request):
    """Render the rewards shop and create party rewards."""

    selected_guid = request.GET.get("guid") or request.POST.get("guid")
    selected_party = getPartyDetails(request.user, selected_guid) if selected_guid else None

    if selected_guid and selected_party is None:
        messages.error(request, "Party not found or you do not have access to it.")
        return redirect("QuestLog:rewards")

    if selected_party is None:
        selected_party = request.user.parties.order_by("party_name").first()

    if selected_party is None:
        context = {
            "party_leaderboards": genLeaderboard(request.user),
            "parties": getParties(request.user),
            "pending_party_invitations": getPendingPartyInvitations(request.user),
            "party": None,
            "reward_form": RewardForm(),
        }
        context.update(get_profile_customization_context(request.user))
        return render(request, "rewards.html", context)

    ensure_party_reward_catalog(selected_party, selected_party.creator)
    user_points = get_or_create_user_points(request.user, selected_party)
    reward_form = RewardForm()

    if request.method == "POST":
        if selected_party.creator_id != request.user.id:
            messages.error(request, "Only the party creator can add rewards.")
            return redirect(f"{reverse('QuestLog:rewards')}?guid={selected_party.guid}")

        reward_form = RewardForm(request.POST)
        if reward_form.is_valid():
            reward = reward_form.save(commit=False)
            reward.party = selected_party
            reward.created_by = request.user
            reward.class_attributes = reward.name
            reward.save()
            messages.success(request, f"{reward.name} was added to {selected_party.party_name}.")
            return redirect(f"{reverse('QuestLog:rewards')}?guid={selected_party.guid}")

    reward_catalog = (
        Reward.objects
        .filter(Q(party=selected_party) | Q(party__isnull=True), is_active=True, point_cost__gt=0)
        .order_by("point_cost", "name", "class_attributes")
    )
    purchased_rewards = (
        RewardPurchase.objects
        .filter(user=request.user, party=selected_party)
        .select_related("reward")
    )

    context = {
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "party": selected_party,
        "user_points": user_points,
        "reward_catalog": reward_catalog,
        "purchased_rewards": purchased_rewards,
        "reward_form": reward_form,
    }
    context.update(get_profile_customization_context(request.user))
    return render(request, "rewards.html", context)


@login_required(login_url="QuestLog:login")
@require_POST
def purchase_reward(request, reward_id):
    """Redeem a reward for points."""

    reward = get_object_or_404(
        Reward.objects.select_related("party"),
        pk=reward_id,
        is_active=True,
        point_cost__gt=0,
    )

    party = reward.party
    if party is None:
        guid = request.POST.get("guid")
        party = getPartyDetails(request.user, guid) if guid else None
        if party is None:
            messages.error(request, "Choose a party before redeeming that reward.")
            return redirect("QuestLog:rewards")
    elif not party.members.filter(pk=request.user.pk).exists():
        raise Http404("Reward not found.")

    redirect_to_rewards = f"{reverse('QuestLog:rewards')}?guid={party.guid}"

    with transaction.atomic():
        user_points = get_or_create_user_points(request.user, party, for_update=True)

        if user_points.available_points < reward.point_cost:
            messages.error(
                request,
                f"You need {reward.point_cost} points to redeem {reward.label}.",
            )
            return redirect(redirect_to_rewards)

        user_points.spent_points += reward.point_cost
        user_points.rewards = reward
        user_points.save(update_fields=["spent_points", "rewards"])
        profile_updated = reward.apply_to_profile(request.user)

        RewardPurchase.objects.create(
            user=request.user,
            party=party,
            reward=reward,
            points_spent=reward.point_cost,
        )

    message = f"{reward.label} redeemed for {reward.point_cost} points."
    if profile_updated:
        message += " Your profile was updated."
    messages.success(request, message)
    return redirect(redirect_to_rewards)


@login_required(login_url="QuestLog:login")
def parties(request):
    """Render parties for the current user."""

    return renderPage(request, "parties.html")


@login_required(login_url="QuestLog:login")
def create_task(request):
    """Create a task for a party."""

    selected_party = None
    selected_guid = request.GET.get("guid") or request.POST.get("guid")
    if selected_guid:
        selected_party = getPartyDetails(request.user, selected_guid)
        if selected_party is None:
            messages.error(request, "Party not found or you do not have access to it.")
            return redirect("QuestLog:tasks")

    if not request.user.parties.exists():
        messages.warning(request, "Join or create a party before adding tasks.")
        return redirect("QuestLog:create_party")

    form = CreateTaskForm(user=request.user, selected_party=selected_party)

    if request.method == "POST":
        form = CreateTaskForm(request.POST, user=request.user, selected_party=selected_party)
        if form.is_valid():
            with transaction.atomic():
                task = form.save(commit=False)
                task.owner = request.user
                task.point_value = task.difficulty_rating * 10
                task.save()

                TaskDifficultyVote.objects.update_or_create(
                    task=task,
                    voter=request.user,
                    defaults={"rating": task.difficulty_rating},
                )
                task.sync_point_value_with_difficulty()

            messages.success(request, f"{task.name} was added to {task.affiliation.party_name}.")
            return redirect(f"{reverse('QuestLog:tasks')}?guid={task.affiliation.guid}")

    context = {
        "profile": get_user_profile(request.user),
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "form": form,
        "selected_party": selected_party,
    }
    return render(request, "create_task.html", context)


@login_required(login_url="QuestLog:login")
@require_POST
def vote_task_difficulty(request, task_id):
    """Save a user's task difficulty vote."""

    task = get_object_or_404(
        Task.objects.select_related("affiliation"),
        pk=task_id,
        affiliation__members=request.user,
    )
    form = TaskDifficultyVoteForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Choose a difficulty rating between 1 and 10.")
        return redirect(f"{reverse('QuestLog:tasks')}?guid={task.affiliation.guid}")

    with transaction.atomic():
        TaskDifficultyVote.objects.update_or_create(
            task=task,
            voter=request.user,
            defaults={"rating": form.cleaned_data["rating"]},
        )
        task.sync_point_value_with_difficulty()

    if task.affiliation.members.count() > 1:
        messages.success(request, f"Difficulty vote saved for {task.name}.")
    else:
        messages.success(request, f"Difficulty updated for {task.name}.")

    return redirect(f"{reverse('QuestLog:tasks')}?guid={task.affiliation.guid}")


@login_required(login_url="QuestLog:login")
def party_details(request):
    """Render and update party details."""

    guid = request.GET.get("guid")
    party = getPartyDetails(request.user, guid) if guid else None

    if party is None:
        messages.error(request, "Party not found or you do not have access to it.")
        return redirect("QuestLog:parties")

    invite_form = InviteUserForm(party=party, invited_by=request.user)

    if request.method == "POST":
        invite_form = InviteUserForm(request.POST, party=party, invited_by=request.user)
        if invite_form.is_valid():
            invited_user = invite_form.invited_user

            with transaction.atomic():
                invitation, created = PartyInvitation.objects.get_or_create(
                    party=party,
                    invited_user=invited_user,
                    defaults={
                        "invited_by": request.user,
                        "status": PartyInvitation.Status.PENDING,
                    },
                )

                if created:
                    messages.success(
                        request,
                        f"{invited_user.username} has been invited to {party.party_name}.",
                    )
                else:
                    if invitation.status == PartyInvitation.Status.PENDING:
                        messages.warning(
                            request,
                            f"{invited_user.username} already has a pending invitation.",
                        )
                    elif invitation.status == PartyInvitation.Status.ACCEPTED:
                        messages.warning(
                            request,
                            f"{invited_user.username} is already in this party.",
                        )
                    else:
                        invitation.status = PartyInvitation.Status.PENDING
                        invitation.invited_by = request.user
                        invitation.responded_at = None
                        invitation.save(update_fields=["status", "invited_by", "responded_at"])
                        messages.success(
                            request,
                            f"A new invitation was sent to {invited_user.username}.",
                        )

                return redirect(f"{reverse('QuestLog:party_details')}?guid={party.guid}")

    context = {
        "profile": get_user_profile(request.user),
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "party": party,
        "members": getPartyMembers(party),
        "tasks": getPartyTasks(party),
        "invite_form": invite_form,
        "pending_invites_for_party": (
            PartyInvitation.objects
            .filter(party=party, status=PartyInvitation.Status.PENDING)
            .select_related("invited_user", "invited_by")
            .order_by("-created_at")
        ),
    }
    return render(request, "party_details.html", context)


@login_required(login_url="QuestLog:login")
def create_party(request):
    """Create a new party."""

    form = CreatePartyForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        party_name = form.cleaned_data["party_name"]
        invited_username = form.cleaned_data["invited_username"].strip()

        with transaction.atomic():
            # create party
            party = Party.objects.create(
                party_name=party_name,
                creator=request.user,
            )

            # creator should automatically be added to their own party
            party.members.add(request.user)

            # creator should have a userpoints row for this party
            get_or_create_user_points(request.user, party)
            ensure_party_reward_catalog(party, request.user)

            # optional invite during creation
            if invited_username:
                try:
                    invited_user = User.objects.get(username=invited_username)
                except User.DoesNotExist:
                    invited_user = None

                if invited_user is None:
                    messages.warning(
                        request,
                        "Party created, but the invited username was not found.",
                    )
                elif invited_user.pk == request.user.pk:
                    messages.warning(request, "Party created. You cannot invite yourself.")
                elif party.members.filter(pk=invited_user.pk).exists():
                    messages.warning(request, "Party created. That user is already a member.")
                else:
                    PartyInvitation.objects.get_or_create(
                        party=party,
                        invited_user=invited_user,
                        defaults={
                            "invited_by": request.user,
                            "status": PartyInvitation.Status.PENDING,
                        },
                    )
                    messages.success(
                        request,
                        f"Party created successfully and {invited_user.username} was invited.",
                    )
                    return redirect(f"{reverse('QuestLog:party_details')}?guid={party.guid}")

        messages.success(request, "Party created successfully.")
        return redirect(f"{reverse('QuestLog:party_details')}?guid={party.guid}")

    context = {
        "profile": get_user_profile(request.user),
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "form": form,
    }
    return render(request, "create_party.html", context)


@login_required(login_url="QuestLog:login")
@require_POST
def accept_party_invitation(request, invitation_id):
    """Accept a pending party invitation."""

    invitation = get_object_or_404(
        PartyInvitation.objects.select_related("party", "invited_user"),
        pk=invitation_id,
        invited_user=request.user,
    )

    if invitation.status != PartyInvitation.Status.PENDING:
        messages.warning(request, "That invitation has already been handled.")
        return redirect("QuestLog:profile")

    with transaction.atomic():
        invitation.party.members.add(request.user)

        get_or_create_user_points(request.user, invitation.party)
        ensure_party_reward_catalog(invitation.party, invitation.party.creator)

        invitation.status = PartyInvitation.Status.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

    messages.success(request, f"You joined {invitation.party.party_name}.")
    return redirect("QuestLog:profile")


@login_required(login_url="QuestLog:login")
@require_POST
def decline_party_invitation(request, invitation_id):
    """Decline a pending party invitation."""

    invitation = get_object_or_404(
        PartyInvitation.objects.select_related("party", "invited_user"),
        pk=invitation_id,
        invited_user=request.user,
    )

    if invitation.status != PartyInvitation.Status.PENDING:
        messages.warning(request, "That invitation has already been handled.")
        return redirect("QuestLog:profile")

    invitation.status = PartyInvitation.Status.DECLINED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at"])

    messages.info(request, f"You declined the invitation to {invitation.party.party_name}.")
    return redirect("QuestLog:profile")

MAX_FILE_SIZE = 5*1024*1024
IMAGE_TYPES = ["image/avif", "image/gif", "image/bmp", "image/jpeg", "image/png", "image/webp"]

@require_POST
def upload_task_proof(request):
    """Upload proof and complete a task."""

    if not request.user.is_authenticated:
        return redirect("QuestLog:login")

    file1 = request.FILES.get("proof_file")
    task_id = request.POST.get("task_id")
    task = (
        Task.objects.filter(id=task_id, owner=request.user)
        .exclude(status=Task.Status.COMPLETED)
        .first()
    )

    if task is None:
        messages.error(request, "Task not found.")
        return redirect("QuestLog:tasks")

    if not file1:
        messages.error(request, "No file uploaded.")
        return redirect(f"{reverse('QuestLog:complete_task')}?task_id={task.id}")

    #is image file type
    content_type = file1.content_type
    if content_type not in IMAGE_TYPES:
        messages.error(request, "Unsupported format")
        return redirect(f"{reverse('QuestLog:complete_task')}?task_id={task.id}")

    #greater than X
    if file1.size > MAX_FILE_SIZE:
        messages.error(request, "Image to large")
        return redirect(f"{reverse('QuestLog:complete_task')}?task_id={task.id}")

    with transaction.atomic():
        task.proofs = file1
        task.status = Task.Status.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=["proofs", "status", "completed_at"])
    user_points = get_or_create_user_points(request.user, task.affiliation)
    user_points.points += task.point_value
    user_points.save(update_fields=["points"])

    return redirect(f"{reverse('QuestLog:tasks')}?guid={task.affiliation.guid}")
