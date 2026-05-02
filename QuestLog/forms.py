"""Forms for Quest Log account, party, task, and reward flows."""

# pylint: disable=no-member,too-few-public-methods,too-many-ancestors

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Party, Reward, Task, UserPoints, save_user_profile

User = get_user_model()
DEFAULT_MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024
DEFAULT_ALLOWED_PROFILE_PICTURE_FORMATS = frozenset({"GIF", "JPEG", "PNG", "WEBP"})


def get_max_profile_picture_size():
    """Return the configured profile picture size limit."""

    configured_size = getattr(
        settings,
        "MAX_PROFILE_PICTURE_SIZE",
        DEFAULT_MAX_PROFILE_PICTURE_SIZE,
    )
    if not isinstance(configured_size, int) or configured_size <= 0:
        return DEFAULT_MAX_PROFILE_PICTURE_SIZE
    return configured_size


def get_allowed_profile_picture_formats():
    """Return allowed profile picture image formats."""

    configured_formats = getattr(
        settings,
        "ALLOWED_PROFILE_PICTURE_FORMATS",
        DEFAULT_ALLOWED_PROFILE_PICTURE_FORMATS,
    )
    try:
        normalized_formats = {str(image_format).upper() for image_format in configured_formats}
    except TypeError:
        return DEFAULT_ALLOWED_PROFILE_PICTURE_FORMATS

    normalized_formats.discard("")
    return normalized_formats or DEFAULT_ALLOWED_PROFILE_PICTURE_FORMATS


class QuestLogUserCreationForm(UserCreationForm):
    """Registration form that also creates a user profile."""

    display_name = forms.CharField(max_length=150)
    profile_picture = forms.ImageField(required=False)

    class Meta(UserCreationForm.Meta):
        """Fields for registration."""

        model = User
        fields = ("display_name", "username", "email", "profile_picture")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].widget.attrs["placeholder"] = "Choose a display name"
        self.fields["username"].widget.attrs["placeholder"] = "Choose a username"
        self.fields["email"].widget.attrs["placeholder"] = "Enter your email"
        self.fields["profile_picture"].required = False
        self.fields["profile_picture"].widget.attrs["accept"] = "image/*"
        self.fields["password1"].widget.attrs["placeholder"] = "Create a password"
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm your password"
        self.order_fields(
            ["display_name", "username", "email", "profile_picture", "password1", "password2"]
        )

    def save(self, commit=True):
        """Save the user and profile."""

        user = super().save(commit=False)

        if commit:
            user.save()
            self.save_profile(user)

        return user

    def save_profile(self, user):
        """Save the profile fields for a new user."""

        return save_user_profile(
            user,
            display_name=self.cleaned_data["display_name"],
            profile_picture=self.cleaned_data.get("profile_picture"),
        )

    def clean_profile_picture(self):
        """Validate uploaded profile pictures."""

        profile_picture = self.cleaned_data.get("profile_picture")
        if not profile_picture:
            return profile_picture

        if profile_picture.size > get_max_profile_picture_size():
            raise forms.ValidationError("Profile pictures must be 5 MB or smaller.")

        image = getattr(profile_picture, "image", None)
        image_format = getattr(image, "format", "")
        if image_format not in get_allowed_profile_picture_formats():
            raise forms.ValidationError("Unsupported profile picture file type.")

        return profile_picture


class QuestLogAuthenticationForm(AuthenticationForm):
    """Login form with Quest Log placeholders."""

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "Enter your username"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}),
    )

class CreatePartyForm(forms.Form):
    """Form for creating a party and optional first invite."""

    party_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Enter a party name"}),
    )
    invited_username = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Optional: invite a user by username"}),
    )

    def clean_party_name(self):
        """Reject blank party names."""

        party_name = self.cleaned_data["party_name"].strip()
        if not party_name:
            raise forms.ValidationError("Party name cannot be blank.")
        return party_name


class InviteUserForm(forms.Form):
    """Form for inviting an existing user to a party."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Enter a username to invite"}),
    )

    def __init__(self, *args, party=None, invited_by=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.party = party
        self.invited_by = invited_by
        self.invited_user = None

    def clean_username(self):
        """Resolve and validate the invited username."""

        username = self.cleaned_data["username"].strip()

        try:
            invited_user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise forms.ValidationError("No user with that username exists.") from exc

        if self.party and self.party.members.filter(pk=invited_user.pk).exists():
            raise forms.ValidationError("That user is already a member of this party.")

        if self.invited_by and invited_user.pk == self.invited_by.pk:
            raise forms.ValidationError("You cannot invite yourself.")
        #Store the user object for use in the view after form validation
        self.invited_user = invited_user

        return invited_user


class CreateTaskForm(forms.ModelForm):
    """Form for creating party tasks."""

    difficulty_rating = forms.IntegerField(
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(
            attrs={
                "min": 1,
                "max": 10,
                "step": 1,
            }
        ),
    )

    class Meta:
        """Fields for task creation."""

        model = Task
        fields = ("affiliation", "name", "description", "difficulty_rating", "recurring", "bounty")
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Describe what needs to get done.",
                }
            ),
            "name": forms.TextInput(
                attrs={"placeholder": "Enter a task name"}
            ),
            "recurring": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": 1,
                    "placeholder": "0 for non-recurring, or enter the number of days",
                }
            ),
            "bounty": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": 1,
                    "placeholder": "0",
                }
            ),

        }
        labels = {
            "affiliation": "Party",
            "name": "Task name",
            "description": "Task description",
            "difficulty_rating": "Starting difficulty",
            "recurring": "Recurring interval (days)",
            "bounty": "Bounty (optional)",
        }

    def __init__(self, *args, user=None, selected_party=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["affiliation"].queryset = Party.objects.none()

        if user is not None:
            self.fields["affiliation"].queryset = user.parties.order_by("party_name")

        if selected_party is not None:
            self.fields["affiliation"].initial = selected_party

        self.fields["affiliation"].empty_label = "Select a party"
        self.fields["affiliation"].widget.attrs["class"] = "form-select"
        self.fields["name"].widget.attrs["class"] = "form-control"
        self.fields["description"].widget.attrs["class"] = "form-control"
        self.fields["difficulty_rating"].widget.attrs["class"] = "form-control"
        self.fields["recurring"].widget.attrs["class"] = "form-control"
        self.fields["bounty"].widget.attrs["class"] = "form-control"
        self.fields["bounty"].required = False
        self.fields["bounty"].initial = 0

    def clean_affiliation(self):
        """Ensure tasks are only created in the user's parties."""

        party = self.cleaned_data["affiliation"]

        if self.user is None or not self.user.parties.filter(pk=party.pk).exists():
            raise forms.ValidationError("You can only create tasks for parties you belong to.")

        return party

    def clean_name(self):
        """Reject blank task names."""

        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Task name cannot be blank.")
        return name

    def clean_description(self):
        """Reject blank task descriptions."""

        description = self.cleaned_data["description"].strip()
        if not description:
            raise forms.ValidationError("Task description cannot be blank.")
        return description
    def clean_recurring(self):
        """Reject negative recurrence intervals."""

        recurring = self.cleaned_data["recurring"]

        if recurring < 0:
            raise forms.ValidationError("Recurring days cannot be negative.")

        return recurring

    def clean_bounty(self):
        """Reject negative bounties."""

        bounty = self.cleaned_data.get("bounty") or 0
        if bounty < 0:
            raise forms.ValidationError("Bounty cannot be negative.")
        return bounty

    def clean(self):
        """Ensure the user has enough party points to fund a bounty."""

        cleaned_data = super().clean()
        bounty = cleaned_data.get("bounty") or 0
        party = cleaned_data.get("affiliation")
        if bounty > 0 and party and self.user:
            try:
                user_points = UserPoints.objects.get(user=self.user, party=party)
                if user_points.points < bounty:
                    self.add_error(
                        "bounty",
                        (
                            f"Not enough points. You have {user_points.points} points "
                            f"in {party.party_name}."
                        ),
                    )
            except UserPoints.DoesNotExist:
                self.add_error(
                    "bounty",
                    "You don't have any points in this party yet. Complete some tasks first.",
                )
        return cleaned_data

class TaskDifficultyVoteForm(forms.Form):
    """Form for voting on task difficulty."""

    RATING_CHOICES = [(rating, f"{rating}") for rating in range(1, 11)]

    rating = forms.TypedChoiceField(
        coerce=int,
        choices = RATING_CHOICES,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )


class RewardForm(forms.ModelForm):
    """Form for party reward catalog entries."""

    class Meta:
        """Fields for reward creation."""

        model = Reward
        fields = ("name", "description", "point_cost", "reward_type", "profile_value")
        labels = {
            "name": "Reward name",
            "description": "Description",
            "point_cost": "Point cost",
            "reward_type": "Reward type",
            "profile_value": "Profile text",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Pick dinner, choose the movie, skip a chore",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "What does the reward unlock?",
                }
            ),
            "point_cost": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "step": 1,
                }
            ),
            "reward_type": forms.Select(attrs={"class": "form-select"}),
            "profile_value": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Quest Champion, Legendary Helper",
                }
            ),
        }
        help_texts = {
            "profile_value": "Required for profile title and calling card rewards.",
        }

    def clean_name(self):
        """Reject blank reward names."""

        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Reward name cannot be blank.")
        return name

    def clean_description(self):
        """Normalize reward descriptions."""

        return self.cleaned_data.get("description", "").strip()

    def clean_point_cost(self):
        """Require a positive reward cost."""

        point_cost = self.cleaned_data["point_cost"]
        if point_cost < 1:
            raise forms.ValidationError("Reward cost must be at least 1 point.")
        return point_cost

    def clean_profile_value(self):
        """Normalize profile reward text."""

        return self.cleaned_data.get("profile_value", "").strip()

    def clean(self):
        """Require profile text for profile rewards."""

        cleaned_data = super().clean()
        reward_type = cleaned_data.get("reward_type")
        profile_value = cleaned_data.get("profile_value", "")

        if reward_type == Reward.RewardType.CUSTOM:
            cleaned_data["profile_value"] = ""
            return cleaned_data

        if reward_type in {Reward.RewardType.PROFILE_TITLE, Reward.RewardType.CALLING_CARD}:
            if not profile_value:
                self.add_error(
                    "profile_value",
                    "Enter the text that should appear on the profile.",
                )

        return cleaned_data
