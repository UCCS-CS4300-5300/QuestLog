from rest_framework import serializers
from django.conf import settings

from .models import UserProfile

class updateProfile(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['user', 'display_name']
