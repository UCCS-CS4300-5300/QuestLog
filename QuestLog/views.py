from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, response
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import escape_leading_slashes, url_has_allowed_host_and_scheme
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from .forms import QuestLogAuthenticationForm, QuestLogUserCreationForm
from .models import UserProfile, get_user_display_name, get_user_profile, genLeaderboard, getParties, getPartyTasks, getPartyMembers
from .serializers import updateUser, updateProfile, updateUser

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
        }
        guid = request.GET.get("guid") or request.GET.get("party") #check to see if there is a party specified
        if guid:
            data["party"] = getPartyDetails(request.user, guid)
            data["party_members"] = getPartyMembers(data["party"])
            data["party_tasks"] = getPartyTasks(data["party"])

        return render(request, page, data)
    else:

        return render(request, page)

def home(request):
    return renderPage(request, "home.html")


def about(request):
    return renderPage(request, "about.html")


def tasks(request):
    return renderPage(request, "tasks.html")


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
            userPro = UserProfile.objects.get(pk=request.user.pk)
            userProfileSerializer = updateProfile(userPro, data=data, partial=True)
            userSerializer = updateUser(request.user, data=data, partial=True)
            if userProfileSerializer.is_valid() and userSerializer.is_valid():
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
    return renderPage(request, "party_details.html")

@login_required(login_url="QuestLog:login")
def create_party(request):
    return renderPage(request, "create_party.html")


def upload_task_proof(request):
    return render(request, 'upload_task_proof.html')
