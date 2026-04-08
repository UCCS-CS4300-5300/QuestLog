from rest_framework import serializers
from django.conf import settings

from .models import UserProfile

class updateProfile(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['user', 'display_name']

    def create(self, validated_data):
        return UserProfile.objects.create(**validated_data)  # For Django models

    def update(self, instance, validated_data):
        instance.user = validated_data.get('user', instance.user)
        instance.display_name = validated_data.get('display_name', instance.display_name)
        return instance
