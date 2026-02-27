from django.urls import path
from . import views

app_name = 'QuestLog'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('tasks/', views.tasks, name='tasks'),
    path('complete_task/', views.complete_task, name='complete_task'),
]
