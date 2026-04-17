from django.urls import path
from . import views

app_name = 'QuestLog'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('tasks/', views.tasks, name='tasks'),
    path('tasks_history/', views.task_history, name='task_history'),
    path('complete_task/', views.complete_task, name='complete_task'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),


    # path('create_task/', views.create_task, name='create_task'),
    path('parties/', views.parties, name='parties'), #join lives here
    path('party_details/', views.party_details, name='party_details'), #MAY NEED TO BE /parties/guid/ 
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('create_party/', views.create_party, name='create_party'),
    path('upload/', views.upload_task_proof, name='upload_task_proof'),

]
