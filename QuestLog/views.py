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
