from django.urls import path
from . import views

app_name = 'QuestLog'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('tasks/', views.tasks, name='tasks'),
<<<<<<< HEAD
<<<<<<< HEAD
    path('complete_task/', views.complete_task, name='complete_task'),
<<<<<<< HEAD
    path('create_task/', views.create_task, name='complete_task'),
    path('parties/', views.parties, name='tasks'), #join lives here
    path('party_details/', views.party_details, name='tasks'),
    path('leaderboard/', views.leaderboard, name='tasks'),
    path('create_party/', views.create_party, name='complete_task'),
    # path('create_party/', views.complete_task, name='complete_task'),

=======
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
<<<<<<< HEAD
>>>>>>> 98ae343 (Add account sign up/log in UI pages and empty profile skeleton)
=======
=======
    path('complete_task', views.complete_task, name='complete_task'),
    path('create_task', views.create_task, name='complete_task'),
    path('parties', views.parties, name='tasks'), #join lives here
    path('party_details', views.party_details, name='tasks'),
    path('leaderboard', views.leaderboard, name='tasks'),
    path('create_party', views.create_party, name='complete_task'),
=======
    path('complete_task/', views.complete_task, name='complete_task'),
    path('create_task/', views.create_task, name='complete_task'),
    path('parties/', views.parties, name='tasks'), #join lives here
    path('party_details/', views.party_details, name='tasks'),
    path('leaderboard/', views.leaderboard, name='tasks'),
    path('create_party/', views.create_party, name='complete_task'),
>>>>>>> 3dd33f0 (fix url path, forgot to add backslash)
    # path('create_party/', views.complete_task, name='complete_task'),

>>>>>>> 3667ca8 (Added URLS.py that did not get pushed in the last commit)
>>>>>>> d0ffc19 (Added URLS.py that did not get pushed in the last commit)
]


