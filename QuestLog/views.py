from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http.request import split_domain_port, validate_host
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import QuestLogAuthenticationForm, QuestLogUserCreationForm
from .models import get_user_display_name, get_user_profile


def get_safe_redirect(request):
    redirect_to = request.POST.get("next") or request.GET.get("next")

    if not redirect_to:
        return reverse("QuestLog:profile")

    redirect_parts = urlsplit(redirect_to)
    candidate_host = redirect_parts.netloc or request.get_host()

    if not url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={candidate_host},
        require_https=request.is_secure(),
    ):
        return reverse("QuestLog:profile")

    if not redirect_parts.netloc:
        return redirect_to

    allowed_hosts = set(settings.ALLOWED_HOSTS)
    current_host, _ = split_domain_port(request.get_host())
    if current_host:
        allowed_hosts.add(current_host)

    redirect_host, _ = split_domain_port(redirect_parts.netloc)
    if redirect_host and validate_host(redirect_host, allowed_hosts):
        return redirect_to

    return reverse("QuestLog:profile")


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
def profile(request):
    return render(
        request,
        "profile.html",
        {
            "profile_user": request.user,
            "profile": get_user_profile(request.user),
        },
    )
