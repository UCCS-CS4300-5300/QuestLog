from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import escape_leading_slashes, url_has_allowed_host_and_scheme

from .forms import QuestLogAuthenticationForm, QuestLogUserCreationForm
from .models import UserProfile, Task, get_user_display_name, get_user_profile, genLeaderboard, getParties, getPartyTasks, getPartyMembers

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
    data = {}
    if request.user.is_authenticated:
        data["tasks"] = (
            Task.objects.filter(owner=request.user)
            .exclude(status=Task.Status.COMPLETED)
            .order_by("status", "-created_at")
        )
    else:
        data["tasks"] = Task.objects.none()
    return render(request, "tasks.html", data)


def task_history(request):
    data = {}
    if request.user.is_authenticated:
        data["tasks"] = (
            Task.objects.filter(owner=request.user, status=Task.Status.COMPLETED)
            .order_by("-completed_at", "-created_at")
        )
    else:
        data["tasks"] = Task.objects.none()
    return render(request, "tasks_history.html", data)


def complete_task(request):
    if not request.user.is_authenticated:
        return redirect("QuestLog:login")

    task_id = request.GET.get("task_id")
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

    is_known_profile_picture = UserProfile.objects.filter(
        profile_picture=normalized_request_path
    ).exists()
    is_known_task_proof = Task.objects.filter(proofs=normalized_request_path).exists()

    if not (is_known_profile_picture or is_known_task_proof):
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
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("QuestLog:login")

        file = request.FILES.get("proof_file")
        task_id = request.POST.get("task_id")
        task = (
            Task.objects.filter(id=task_id, owner=request.user)
            .exclude(status=Task.Status.COMPLETED)
            .first()
        )

        if task is None:
            messages.error(request, "Task not found.")
            return redirect("QuestLog:tasks")

        if not file:
            messages.error(request, "No file uploaded.")
            return redirect(f"{reverse('QuestLog:complete_task')}?task_id={task.id}")

        task.proofs = file
        task.status = Task.Status.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=["proofs", "status", "completed_at"])

        return redirect("QuestLog:tasks")


    return HttpResponse("Only POST allowed")
   
