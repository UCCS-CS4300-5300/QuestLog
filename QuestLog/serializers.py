from rest_framework import serializers
from django.conf import settings

from .models import UserProfile

class updateProfile(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['display_name']

    def update(self, instance, validated_data):
        instance.display_name = validated_data.get('display_name', instance.display_name)
        instance.save()
        return instance
