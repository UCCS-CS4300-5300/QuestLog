from rest_framework import serializers
from django.conf import settings

from .models import UserProfile

from django.contrib.auth import get_user_model
User = get_user_model()

class updateUser(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email']
    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.save()
        return instance

class updateProfile(serializers.ModelSerializer):
    user = updateUser()

    class Meta:
        model = UserProfile
        fields = ['user','display_name']

    def update(self, instance, validated_data):
        instance.display_name = validated_data.get('display_name', instance.display_name)
        instance.save()
        return instance
