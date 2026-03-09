from django.shortcuts import render

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
    return render(request, 'parties.html')

def party_details(request):
    return render(request, 'party_details.html')

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
