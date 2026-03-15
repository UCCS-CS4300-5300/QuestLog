from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import escape_leading_slashes, url_has_allowed_host_and_scheme

from .forms import QuestLogAuthenticationForm, QuestLogUserCreationForm
from .models import UserProfile, get_user_display_name, get_user_profile, Task, Party


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
    default_redirect = reverse("QuestLog:profile")

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


def home(request):
    return render(request, "home.html")


def about(request):
    return render(request, "about.html")


def tasks(request):
    return render(request, "tasks.html")


def complete_task(request):
    return render(request, "complete_task.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("QuestLog:profile")

    form = QuestLogAuthenticationForm(request, data=request.POST or None)
    redirect_to = get_safe_redirect(request)

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, f"Welcome back, {get_user_display_name(form.get_user())}.")
        return redirect(redirect_to)

    return render(request, "login.html", {"form": form, "next": redirect_to})


def register(request):
    if request.user.is_authenticated:
        return redirect("QuestLog:profile")

    form = QuestLogUserCreationForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect("QuestLog:profile")

    return render(request, "register.html", {"form": form})


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
    return render(
        request,
        "profile.html",
        {
            "profile_user": request.user,
            "profile": get_user_profile(request.user),
        },
    )

def parties(request):
    user_parties = Party.objects.none()
    if request.user.is_authenticated:
        user_parties = (
            request.user.parties.all()
            .order_by("party_name")
        )

    return render(request, 'parties.html', {"parties": user_parties})

def party_details(request):
    if not request.user.is_authenticated:
        raise Http404("log in first.")
    guid = request.GET.get("guid") or request.GET.get("party")
    if not guid:
        raise Http404("Party not specified.")

    try:
        party = Party.objects.prefetch_related("members").get(guid=guid)
    except Party.DoesNotExist as e:
        raise Http404("Party not found.") from e

    if request.user.is_authenticated and not party.members.filter(pk=request.user.pk).exists():
        raise Http404("Party not found.")

    tasks_qs = (
        Task.objects.filter(affiliation=party)
        .select_related("owner")
        .order_by("status", "-created_at")
    )

    return render(
        request,
        'party_details.html',
        {
            "party": party,
            "members": party.members.all().order_by("username"),
            "tasks": tasks_qs,
        },
    )

def create_party(request):
    return render(request, 'create_party.html')
def leaderboard(request):
    return render(request, 'leaderboard.html')
