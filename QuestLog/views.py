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

from .forms import QuestLogAuthenticationForm, QuestLogUserCreationForm, CreatePartyForm, InviteUserForm
from .models import UserProfile, Party,PartyInvitation, Reward, UserPoints,Task,get_user_display_name, get_user_profile, genLeaderboard, getParties, getPartyDetails, getPartyTasks, getPartyMembers, getPendingPartyInvitations
from .serializers import updateUser, updateProfile

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


@login_required(login_url="QuestLog:login")
def tasks(request):
    # if missing then show the party selection screen
    guid =request.GET.get("guid")
    if not guid:
        return renderPage(request, "tasks.html")
    #if theres a party selected then verify membership and build task pool context
    party =getPartyDetails(request.user, guid)
    if party is None:
        messages.error(request, "Party not found or perhaps you do not have access to it")
        return redirect("QuestLog:tasks")

    all_tasks =getPartyTasks(party)
    context={
        "profile": get_user_profile(request.user) ,
        "party_leaderboards": genLeaderboard(request.user),
        "parties": getParties(request.user) ,
        "pending_party_invitations": getPendingPartyInvitations(request.user),
        "party": party,
        "available_tasks": all_tasks.filter(status=Task.Status.NOT_STARTED) , }
    return render(request, "tasks.html",context)


def complete_task(request):
    return renderPage(request, "complete_task.html")


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
    if len(path_parts) < 2 or path_parts[0] != "profile_pictures":
        raise Http404("Media file not found.")

    if not UserProfile.objects.filter(profile_picture=normalized_request_path).exists():
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


def upload_task_proof(request):
    return render(request, 'upload_task_proof.html')
