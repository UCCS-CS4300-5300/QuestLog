from django.urls import path
from . import views

app_name = 'QuestLog'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('tasks/', views.tasks, name='tasks'),
    path('complete_task', views.complete_task, name='complete_task'),
    path('create_task', views.create_task, name='complete_task'),
    path('parties', views.parties, name='tasks'), #join lives here
    path('party_details', views.party_details, name='tasks'),
    path('leaderboard', views.leaderboard, name='tasks'),
    path('create_party', views.create_party, name='complete_task'),
    # path('create_party/', views.complete_task, name='complete_task'),

]


