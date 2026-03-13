from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import escape_leading_slashes, is_same_domain, url_has_allowed_host_and_scheme

from .forms import QuestLogAuthenticationForm, QuestLogUserCreationForm
from .models import get_user_display_name, get_user_profile


def get_redirect_allowed_hosts(request):
    request_host = request.get_host()
    request_hostname = urlsplit(f"//{request_host}").hostname
    allowed_patterns = {host for host in settings.ALLOWED_HOSTS if host}
    exact_hosts = {request_host}
    if request_hostname:
        exact_hosts.add(request_hostname)
    return exact_hosts, allowed_patterns


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

    exact_hosts, allowed_patterns = get_redirect_allowed_hosts(request)
    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts=exact_hosts,
        require_https=request.is_secure(),
    ):
        return escape_leading_slashes(redirect_to)

    redirect_host = redirect_parts.hostname
    if (
        redirect_parts.scheme
        and redirect_host
        and any(pattern == "*" or is_same_domain(redirect_host, pattern) for pattern in allowed_patterns)
        and url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={redirect_host, redirect_parts.netloc},
            require_https=request.is_secure(),
        )
    ):
        return redirect_to

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


@login_required(login_url="QuestLog:login")
def serve_media(request, path):
    user_profile = get_user_profile(request.user)
    if not user_profile.profile_picture or path != user_profile.profile_picture.name:
        raise Http404("Media file not found.")

    media_root = Path(settings.MEDIA_ROOT).resolve()

    try:
        media_path = (media_root / path).resolve()
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
