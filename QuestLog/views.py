from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import QuestLogAuthenticationForm, QuestLogUserCreationForm


def get_safe_redirect(request):
    redirect_to = request.POST.get("next") or request.GET.get("next")

    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
    ):
        return redirect_to

    return reverse('QuestLog:profile')


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
    if request.user.is_authenticated:
        return redirect('QuestLog:profile')

    form = QuestLogAuthenticationForm(request, data=request.POST or None)
    redirect_to = get_safe_redirect(request)

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, f"Welcome back, {form.get_user().display_name}.")
        return redirect(redirect_to)

    return render(request, 'login.html', {'form': form, 'next': redirect_to})

def register(request):
    if request.user.is_authenticated:
        return redirect('QuestLog:profile')

    form = QuestLogUserCreationForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect('QuestLog:profile')

    return render(request, 'register.html', {'form': form})

@login_required(login_url='QuestLog:login')
def profile(request):
    return render(request, 'profile.html', {'profile_user': request.user})
