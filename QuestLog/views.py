from django.shortcuts import render
from django.http import Http404

from .models import Party, Task

# Create your views here.
def home(request):
    return render(request, 'home.html')

def about(request):
    return render(request, 'about.html')

def tasks(request):
    return render(request, 'tasks.html')

def complete_task(request):
    return render(request, 'complete_task.html')

def create_task(request):
    return render(request, 'create_task.html')

def parties(request):
    user_parties = Party.objects.none()
    if request.user.is_authenticated:
        user_parties = (
            request.user.parties.all()
            .order_by("party_name")
        )

    return render(request, 'parties.html', {"parties": user_parties})

def party_details(request):
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

def leaderboard(request):
    return render(request, 'leaderboard.html')

def create_party(request):
    return render(request, 'create_party.html')

def login_view(request):
    return render(request, 'login.html')

def register(request):
    return render(request, 'register.html')

def profile(request):
    return render(request, 'profile.html')
