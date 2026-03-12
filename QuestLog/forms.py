from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class QuestLogUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("display_name", "username", "email", "profile_picture")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].widget.attrs["placeholder"] = "Choose a display name"
        self.fields["username"].widget.attrs["placeholder"] = "Choose a username"
        self.fields["email"].widget.attrs["placeholder"] = "Enter your email"
        self.fields["profile_picture"].required = True
        self.fields["profile_picture"].widget.attrs["accept"] = "image/*"
        self.fields["password1"].widget.attrs["placeholder"] = "Create a password"
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm your password"
        self.order_fields(
            ["display_name", "username", "email", "profile_picture", "password1", "password2"]
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
