from django import forms
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
