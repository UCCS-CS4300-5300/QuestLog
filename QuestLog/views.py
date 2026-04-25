"""View functions for QuestLog pages and workflows."""
# pylint: disable=missing-function-docstring,invalid-name

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
    TaskCompletionForm,
    TaskDifficultyVoteForm,
)
from .models import (
    Party,
    PartyInvitation,
    Reward,
    RewardPurchase,
    Task,
    TaskDifficultyVote,
    UserPoints,
    UserProfile,
    genLeaderboard,
    get_default_reward,
    get_user_display_name,
    get_user_profile,
    getParties,
    getPartyDetails,
    getPartyMembers,
    getPartyTasks,
    getPendingPartyInvitations,
)
from .serializers import updateUser, updateProfile

User = get_user_model()


def get_or_create_user_points(user, party, for_update=False):
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
    starter_rewards = [
        {
            "name": "Pick the next group activity",
            "description": "Choose the next movie, game, or shared activity for the party.",
            "point_cost": 5,
        },
        {
            "name": "Small treat fund",
            "description": "Redeem points toward a low-cost treat agreed on by the party.",
            "point_cost": 10,
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
                "created_by": created_by,
            },
        )


def get_completion_reward(party):
    reward, _ = Reward.objects.get_or_create(
        party=party,
        class_attributes="Quest Completion Reward",
        defaults={
            "name": "Quest Completion Reward",
            "description": "Awarded when a party member completes a quest with proof.",
            "point_cost": 0,
            "is_active": False,
            "created_by": party.creator,
        },
    )
    return reward


def get_request_hosts(request):
    request_host = request.get_host()
    request_hostname = urlsplit(f"//{request_host}").hostname
    exact_hosts = {request_host.lower()}
    if request_hostname:
        exact_hosts.add(request_hostname.lower())
    return exact_hosts


def get_redirect_allowed_hosts(request):
    exact_hosts = get_request_hosts(request)
    configured_hosts = getattr(settings, "REDIRECT_ALLOWED_HOSTS", [])
    exact_hosts.update(
        host.lower()
        for host in configured_hosts
        if host and host != "*" and not host.startswith(".")
    )
    return exact_hosts


def get_safe_redirect(request):
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

#render a template page
def renderPage(request, page):
    if request.user.is_authenticated:
        data = { #initial data
            "profile": get_user_profile(request.user),
            "party_leaderboards": genLeaderboard(request.user),
            "parties": getParties(request.user),
            "pending_party_invitations": getPendingPartyInvitations(request.user),
        }
        guid = request.GET.get("guid") or request.GET.get("party")
        if guid:
            data["party"] = getPartyDetails(request.user, guid)
            if data["party"] is not None:
                data["members"] = getPartyMembers(data["party"])
                data["tasks"] = getPartyTasks(data["party"])

        return render(request, page, data)

    return render(request, page)


def home(request):
    return renderPage(request, "home.html")


def about(request):
    return renderPage(request, "about.html")


def tasks(request):
    # if missing then show the party selection screen
    guid = request.GET.get("guid")
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


def complete_task(request):
    if not request.user.is_authenticated:
        return renderPage(request, "complete_task.html")

    selected_guid = request.GET.get("guid")
    selected_party = getPartyDetails(request.user, selected_guid) if selected_guid else None
    task_queryset = (
        Task.objects
        .filter(affiliation__members=request.user, status=Task.Status.NOT_STARTED)
        .select_related("affiliation", "owner")
        .order_by("affiliation__party_name", "-created_at")
    )

    if selected_guid and selected_party is None:
        messages.error(request, "Party not found or you do not have access to it.")
        return redirect("QuestLog:tasks")

    if selected_party is not None:
        task_queryset = task_queryset.filter(affiliation=selected_party)

    context = {
        "profile": get_user_profile(request.user),
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "party": selected_party,
        "available_tasks": task_queryset,
    }
    return render(request, "complete_task.html", context)


@login_required(login_url="QuestLog:login")
def complete_task_detail(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related("affiliation", "owner"),
        pk=task_id,
        affiliation__members=request.user,
    )

    redirect_to_tasks = f"{reverse('QuestLog:tasks')}?guid={task.affiliation.guid}"

    if task.status == Task.Status.COMPLETED:
        messages.warning(request, f"{task.name} has already been completed.")
        return redirect(redirect_to_tasks)

    form = TaskCompletionForm(instance=task)

    if request.method == "POST":
        form = TaskCompletionForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            with transaction.atomic():
                locked_task = get_object_or_404(
                    Task.objects.select_for_update().select_related("affiliation"),
                    pk=task_id,
                    affiliation__members=request.user,
                )

                if locked_task.status == Task.Status.COMPLETED:
                    messages.warning(
                        request,
                        f"{locked_task.name} has already been completed.",
                    )
                    return redirect(redirect_to_tasks)

                proof = form.cleaned_data["proofs"]
                locked_task.proofs = proof
                locked_task.status = Task.Status.COMPLETED
                locked_task.completed_by = request.user
                locked_task.completed_at = timezone.now()
                if locked_task.claimed_at is None:
                    locked_task.claimed_at = locked_task.completed_at
                locked_task.save(
                    update_fields=[
                        "proofs",
                        "status",
                        "completed_by",
                        "completed_at",
                        "claimed_at",
                    ]
                )

                user_points = get_or_create_user_points(
                    request.user,
                    locked_task.affiliation,
                    for_update=True,
                )
                user_points.points += locked_task.point_value
                user_points.rewards = get_completion_reward(locked_task.affiliation)
                user_points.save(update_fields=["points", "rewards"])

            messages.success(
                request,
                f"{task.name} completed. You earned {task.point_value} point"
                f"{'s' if task.point_value != 1 else ''} for {task.affiliation.party_name}.",
            )
            return redirect("QuestLog:leaderboard")

    context = {
        "profile": get_user_profile(request.user),
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "task": task,
        "party": task.affiliation,
        "form": form,
    }
    return render(request, "complete_task.html", context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("QuestLog:home")

    form = QuestLogAuthenticationForm(request, data=request.POST or None)
    redirect_to = get_safe_redirect(request)

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(
            request,
            f"Welcome back, {get_user_display_name(form.get_user())}.",
        )
        return redirect(redirect_to)

    return render(request, "login.html", {"form": form, "next": redirect_to})


def register(request):
    if request.user.is_authenticated:
        return redirect("QuestLog:home")

    form = QuestLogUserCreationForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect("QuestLog:home")

    return render(request, "register.html", {"form": form})

#logout
@login_required(login_url="QuestLog:login")
def logout_view(request):
    logout(request)
    return redirect("QuestLog:home")



def normalize_media_path(path):
    return PurePosixPath(
        "/" + unquote(path).replace("\\", "/")
    ).as_posix().lstrip("/")


def serve_media(request, path):
    normalized_request_path = normalize_media_path(path)
    path_parts = PurePosixPath(normalized_request_path).parts
    if len(path_parts) < 2:
        raise Http404("Media file not found.")

    media_type = path_parts[0]
    is_allowed_media = False

    if media_type == "profile_pictures":
        is_allowed_media = UserProfile.objects.filter(
            profile_picture=normalized_request_path
        ).exists()
    elif media_type == "proofs" and request.user.is_authenticated:
        is_allowed_media = Task.objects.filter(
            proofs=normalized_request_path,
            affiliation__members=request.user,
        ).exists()

    if not is_allowed_media:
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
    if request.method == "POST":
        # We attempt to parse the json. Flag indicates success or failure
        flag = True
        try:
            data = json.loads(request.body)
        except ValueError:
            flag = False

        # keys that are allowed
        allowed_keys = {"display_name", "email"}

        #flag is true if json parsed correctly and there are no unauthorized keys
        if flag and set(data).issubset(allowed_keys):
            # Deserialize the auth user and profile as separate models.
            user_profile = UserProfile.objects.get(user=request.user)
            profile_serializer = updateProfile(user_profile, data=data, partial=True)
            user_serializer = updateUser(request.user, data=data, partial=True)
            if profile_serializer.is_valid() and user_serializer.is_valid():
                with transaction.atomic():
                    profile_serializer.save()
                    user_serializer.save()

                resp = Response(
                    profile_serializer.data | user_serializer.data,
                    status=200,
                )
            else:
                resp = Response(
                    profile_serializer.errors | user_serializer.errors,
                    status=400,
                )
        else:
            resp = Response("Bad json or unknown keys", status=400)

        #create response
        resp.accepted_renderer = JSONRenderer()
        resp.accepted_media_type = 'application/json'
        resp.renderer_context = {'request': request}

        return resp
    return renderPage(request, "profile.html")

@login_required(login_url="QuestLog:login")
def leaderboard(request):
    return renderPage(request, "leaderboard.html")


@login_required(login_url="QuestLog:login")
def rewards(request):
    selected_guid = request.GET.get("guid") or request.POST.get("guid")
    selected_party = getPartyDetails(request.user, selected_guid) if selected_guid else None

    if selected_guid and selected_party is None:
        messages.error(request, "Party not found or you do not have access to it.")
        return redirect("QuestLog:rewards")

    if selected_party is None:
        selected_party = request.user.parties.order_by("party_name").first()

    if selected_party is None:
        context = {
            "profile": get_user_profile(request.user),
            "party_leaderboards": genLeaderboard(request.user),
            "parties": getParties(request.user),
            "pending_party_invitations": getPendingPartyInvitations(request.user),
            "party": None,
            "reward_form": RewardForm(),
        }
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
        "profile": get_user_profile(request.user),
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user),
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "party": selected_party,
        "user_points": user_points,
        "reward_catalog": reward_catalog,
        "purchased_rewards": purchased_rewards,
        "reward_form": reward_form,
    }
    return render(request, "rewards.html", context)


@login_required(login_url="QuestLog:login")
@require_POST
def purchase_reward(request, reward_id):
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

        RewardPurchase.objects.create(
            user=request.user,
            party=party,
            reward=reward,
            points_spent=reward.point_cost,
        )

    messages.success(request, f"{reward.label} redeemed for {reward.point_cost} points.")
    return redirect(redirect_to_rewards)


@login_required(login_url="QuestLog:login")
def parties(request):
    return renderPage(request, "parties.html")


@login_required(login_url="QuestLog:login")
def create_task(request):
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
                task.point_value = task.difficulty_rating
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
    task = get_object_or_404(
        Task.objects.select_related("affiliation"),
        pk=task_id,
        affiliation__members=request.user,
    )
    form = TaskDifficultyVoteForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Choose a difficulty rating between 1 and 5.")
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
            UserPoints.objects.get_or_create(
                user=request.user,
                party=party,
                defaults={
                    "points": 0,
                    "rewards": get_default_reward(),
                },
            )
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

        UserPoints.objects.get_or_create(
            user=request.user,
            party=invitation.party,
            defaults={
                "points": 0,
                "rewards": get_default_reward(),
            },
        )
        ensure_party_reward_catalog(invitation.party, invitation.party.creator)

        invitation.status = PartyInvitation.Status.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

    messages.success(request, f"You joined {invitation.party.party_name}.")
    return redirect("QuestLog:profile")


@login_required(login_url="QuestLog:login")
@require_POST
def decline_party_invitation(request, invitation_id):
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


def upload_task_proof(request):
    return render(request, 'upload_task_proof.html')
