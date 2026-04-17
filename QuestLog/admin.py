from django.contrib import admin

from .models import UserProfile, Party, PartyInvitation


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email", "display_name")

@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ("party_name", "guid")
    search_fields = ("party_name", "guid")
    filter_horizontal = ("members",)

@admin.register(PartyInvitation)
class PartyInvitationAdmin(admin.ModelAdmin):
    list_display = ("party", "invited_user", "invited_by", "status", "created_at", "responded_at")
    list_filter = ("status",)
    search_fields = ("party__party_name", "invited_user__username", "invited_by__username")