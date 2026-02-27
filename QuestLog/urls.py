from django.urls import path
from . import views

app_name = 'QuestLog'

urlpatterns = [
    path('', views.home, name='app'),
    path('about/', views.about, name='about'),
]
