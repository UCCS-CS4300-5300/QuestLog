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

def login_view(request):
    return render(request, 'login.html')

def register(request):
    return render(request, 'register.html')

def profile(request):
    return render(request, 'profile.html')