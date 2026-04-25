from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import escape_leading_slashes, url_has_allowed_host_and_scheme
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.db import transaction
from django.views.decorators.http import require_POST
from .forms import CreatePartyForm, CreateTaskForm, InviteUserForm, QuestLogAuthenticationForm, QuestLogUserCreationForm, TaskDifficultyVoteForm
from .models import Party, PartyInvitation, Reward, Task, TaskDifficultyVote, UserPoints, UserProfile, get_user_display_name, get_user_profile, genLeaderboard, getParties, getPartyDetails, getPartyMembers, getPartyTasks, getPendingPartyInvitations
from .serializers import updateUser, updateProfile

from PIL import Image

User = get_user_model()

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
    if(request.user.is_authenticated):
        data = { #initial data
            "profile": get_user_profile(request.user),
            "party_leaderboards": genLeaderboard(request.user),
            "parties": getParties(request.user),
            "pending_party_invitations": getPendingPartyInvitations(request.user),
        }
        guid = request.GET.get("guid") or request.GET.get("party") #check to see if there is a party specified
        if guid:
            data["party"] = getPartyDetails(request.user, guid)
            if data["party"] is not None:
                data["members"] = getPartyMembers(data["party"])
                data["tasks"] = getPartyTasks(data["party"])

        return render(request, page, data)
    else:

        return render(request, page)
    
def home(request):
    return renderPage(request, "home.html")


def about(request):
    return renderPage(request, "about.html")


def tasks(request):
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
    party =getPartyDetails(request.user, guid)
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

    context={
        "profile": get_user_profile(request.user) ,
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user) ,
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "party": party,
        "available_tasks": available_tasks,
        "difficulty_rating_choices": TaskDifficultyVoteForm.RATING_CHOICES,
        "party_member_count": party_member_count,
    }
    return render(request, "tasks.html",context)


def task_history(request):
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
            #deserialize (user and userprofile need two seperate serializers since they are seperate models)
            userPro = UserProfile.objects.get(user=request.user)
            userProfileSerializer = updateProfile(userPro, data=data, partial=True)
            userSerializer = updateUser(request.user, data=data, partial=True)
            if userProfileSerializer.is_valid() and userSerializer.is_valid():
                with transaction.atomic():
                    userProfileSerializer.save()
                    userSerializer.save()

                resp = Response(userProfileSerializer.data | userSerializer.data, status=200)
            else:
                resp = Response(userProfileSerializer.errors | userSerializer.errors, status=400)
        else:
            resp = Response("Bad json or unknown keys", status=400)

        #create response
        resp.accepted_renderer = JSONRenderer()
        resp.accepted_media_type = 'application/json'
        resp.renderer_context = {'request': request}

        return resp
    else:
        return renderPage(request, "profile.html")

@login_required(login_url="QuestLog:login")
def leaderboard(request):
    return renderPage(request, "leaderboard.html")

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
                    messages.success(request, f"{invited_user.username} has been invited to {party.party_name}.")
                else:
                    if invitation.status == PartyInvitation.Status.PENDING:
                        messages.warning(request, f"{invited_user.username} already has a pending invitation.")
                    elif invitation.status == PartyInvitation.Status.ACCEPTED:
                        messages.warning(request, f"{invited_user.username} is already in this party.")
                    else:
                        invitation.status = PartyInvitation.Status.PENDING
                        invitation.invited_by = request.user
                        invitation.responded_at = None
                        invitation.save(update_fields=["status", "invited_by", "responded_at"])
                        messages.success(request, f"A new invitation was sent to {invited_user.username}.")

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
            default_reward, _ = Reward.objects.get_or_create(
                class_attributes="Default Reward"
            )
            UserPoints.objects.get_or_create(
                user=request.user,
                party=party,
                defaults={
                    "points": 0,
                    "rewards": default_reward,
                },
            )

            # optional invite during creation
            if invited_username:
                try:
                    invited_user = User.objects.get(username=invited_username)
                except User.DoesNotExist:
                    invited_user = None

                if invited_user is None:
                    messages.warning(request, "Party created, but the invited username was not found.")
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

        default_reward, _ = Reward.objects.get_or_create(
            class_attributes="Default Reward"
        )
        UserPoints.objects.get_or_create(
            user=request.user,
            party=invitation.party,
            defaults={
                "points": 0,
                "rewards": default_reward,
            },
        )

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

MAX_FILE_SIZE = 5*1024*1024
IMAGE_TYPES = ["image/avif", "image/gif", "image/bmp", "image/jpeg", "image/png", "image/webp"]

@require_POST
def upload_task_proof(request):
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
    if not (content_type in IMAGE_TYPES):
        messages.error(request, "Unsupported format")
        return redirect(f"{reverse('QuestLog:complete_task')}?task_id={task.id}")

    #greater than X
    if file1.size > MAX_FILE_SIZE:
        messages.error(request, "Image to large")
        return redirect(f"{reverse('QuestLog:complete_task')}?task_id={task.id}")

    task.proofs = file1
    task.status = Task.Status.COMPLETED
    task.completed_at = timezone.now()
    task.save(update_fields=["proofs", "status", "completed_at"])

    return redirect("QuestLog:tasks")
   
