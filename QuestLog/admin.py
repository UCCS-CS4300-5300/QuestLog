from django.contrib import admin

from .models import Party, PartyInvitation, Task, TaskDifficultyVote, UserProfile


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


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("name", "affiliation", "owner", "difficulty_rating", "point_value", "status")
    list_filter = ("status", "affiliation")
    search_fields = ("name", "description", "owner__username", "affiliation__party_name")


@admin.register(TaskDifficultyVote)
class TaskDifficultyVoteAdmin(admin.ModelAdmin):
    list_display = ("task", "voter", "rating", "updated_at")
    list_filter = ("rating",)
    search_fields = ("task__name", "voter__username")
