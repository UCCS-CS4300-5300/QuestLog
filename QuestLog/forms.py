from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import save_user_profile

User = get_user_model()


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

        original_upload = self.files.get("profile_picture") or profile_picture

        if original_upload.size > settings.MAX_PROFILE_PICTURE_SIZE:
            raise forms.ValidationError("Profile pictures must be 5 MB or smaller.")

        image = getattr(profile_picture, "image", None)
        content_type = image.get_format_mimetype() if image else ""
        if not content_type:
            content_type = getattr(original_upload, "content_type", "")
        if content_type and content_type not in settings.ALLOWED_PROFILE_PICTURE_CONTENT_TYPES:
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
