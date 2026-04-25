from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Party, Reward, Task, save_user_profile

User = get_user_model()
DEFAULT_MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024
DEFAULT_ALLOWED_PROFILE_PICTURE_FORMATS = frozenset({"GIF", "JPEG", "PNG", "WEBP"})


def get_max_profile_picture_size():
    configured_size = getattr(
        settings,
        "MAX_PROFILE_PICTURE_SIZE",
        DEFAULT_MAX_PROFILE_PICTURE_SIZE,
    )
    if not isinstance(configured_size, int) or configured_size <= 0:
        return DEFAULT_MAX_PROFILE_PICTURE_SIZE
    return configured_size


def get_allowed_profile_picture_formats():
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
    display_name = forms.CharField(max_length=150)
    profile_picture = forms.ImageField(required=False)

    class Meta(UserCreationForm.Meta):
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
        user = super().save(commit=False)

        if commit:
            user.save()
            self.save_profile(user)

        return user

    def save_profile(self, user):
        return save_user_profile(
            user,
            display_name=self.cleaned_data["display_name"],
            profile_picture=self.cleaned_data.get("profile_picture"),
        )

    def clean_profile_picture(self):
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
        party_name = self.cleaned_data["party_name"].strip()
        if not party_name:
            raise forms.ValidationError("Party name cannot be blank.")
        return party_name


class InviteUserForm(forms.Form):
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
        username = self.cleaned_data["username"].strip()

        try:
            invited_user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No user with that username exists.")

        if self.party and self.party.members.filter(pk=invited_user.pk).exists():
            raise forms.ValidationError("That user is already a member of this party.")

        if self.invited_by and invited_user.pk == self.invited_by.pk:
            raise forms.ValidationError("You cannot invite yourself.")
        #Store the user object for use in the view after form validation
        self.invited_user = invited_user

        return invited_user


class CreateTaskForm(forms.ModelForm):
    difficulty_rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.NumberInput(
            attrs={
                "min": 1,
                "max": 5,
                "step": 1,
            }
        ),
    )

    class Meta:
        model = Task
        fields = ("affiliation", "name", "description", "difficulty_rating")
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
        }
        labels = {
            "affiliation": "Party",
            "name": "Task name",
            "description": "Task description",
            "difficulty_rating": "Starting difficulty",
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

    def clean_affiliation(self):
        party = self.cleaned_data["affiliation"]

        if self.user is None or not self.user.parties.filter(pk=party.pk).exists():
            raise forms.ValidationError("You can only create tasks for parties you belong to.")

        return party

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Task name cannot be blank.")
        return name

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if not description:
            raise forms.ValidationError("Task description cannot be blank.")
        return description


class TaskDifficultyVoteForm(forms.Form):
    RATING_CHOICES = [(rating, f"{rating}") for rating in range(1, 6)]

    rating = forms.TypedChoiceField(
        coerce=int,
        choices=RATING_CHOICES,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )


class TaskCompletionForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("proofs",)
        labels = {
            "proofs": "Completion evidence",
        }
        widgets = {
            "proofs": forms.ClearableFileInput(
                attrs={
                    "accept": "image/jpeg,image/png,image/gif",
                    "class": "form-control",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proofs"].required = True
        self.fields["proofs"].error_messages["required"] = (
            "Upload evidence before completing this quest."
        )

    def clean_proofs(self):
        proof = self.cleaned_data.get("proofs")
        if not proof:
            raise forms.ValidationError("Upload evidence before completing this quest.")
        return proof


class RewardForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = ("name", "description", "point_cost")
        labels = {
            "name": "Reward name",
            "description": "Description",
            "point_cost": "Point cost",
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
                    "placeholder": "What does the winner get?",
                }
            ),
            "point_cost": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "step": 1,
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Reward name cannot be blank.")
        return name

    def clean_description(self):
        return self.cleaned_data.get("description", "").strip()

    def clean_point_cost(self):
        point_cost = self.cleaned_data["point_cost"]
        if point_cost < 1:
            raise forms.ValidationError("Reward cost must be at least 1 point.")
        return point_cost
