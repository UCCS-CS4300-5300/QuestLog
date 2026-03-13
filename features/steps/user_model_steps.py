from behave import given, then, when
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from QuestLog.models import get_user_profile


TEST_IMAGE_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


def make_profile_picture():
    return SimpleUploadedFile(
        "avatar.gif",
        TEST_IMAGE_BYTES,
        content_type="image/gif",
    )


def create_user_with_profile(username, display_name, password, profile_picture=None):
    user = get_user_model().objects.create_user(
        username=username,
        password=password,
    )
    profile = get_user_profile(user)
    profile.display_name = display_name
    if profile_picture:
        profile.profile_picture = profile_picture
    profile.save()
    return user


@given(
    'a Quest Log user exists with username "{username}", display name "{display_name}", and password "{password}"'
)
def step_create_existing_user(context, username, display_name, password):
    context.user = create_user_with_profile(username, display_name, password)


@when(
    'I create a Quest Log user with username "{username}", display name "{display_name}", and password "{password}"'
)
def step_create_user(context, username, display_name, password):
    context.user = create_user_with_profile(username, display_name, password)


@when(
    'I create a Quest Log user with username "{username}", display name "{display_name}", password "{password}", and a profile picture'
)
def step_create_user_with_profile_picture(context, username, display_name, password):
    context.user = create_user_with_profile(
        username,
        display_name,
        password,
        profile_picture=make_profile_picture(),
    )


@when(
    'I submit the sign up form for username "{username}", display name "{display_name}", and password "{password}"'
)
def step_submit_signup_form(context, username, display_name, password):
    context.response = context.test.client.post(
        reverse("QuestLog:register"),
        {
            "display_name": display_name,
            "username": username,
            "email": f"{username}@example.com",
            "profile_picture": make_profile_picture(),
            "password1": password,
            "password2": password,
        },
    )


@when('I submit the login form for username "{username}" and password "{password}"')
def step_submit_login_form(context, username, password):
    context.response = context.test.client.post(
        reverse("QuestLog:login"),
        {
            "username": username,
            "password": password,
        },
    )


@given('I am authenticated as "{username}"')
def step_authenticate_existing_user(context, username):
    user = get_user_model().objects.get(username=username)
    context.test.client.force_login(user)


@then('a Quest Log user with username "{username}" should exist')
def step_user_exists(context, username):
    user_model = get_user_model()
    context.user = user_model.objects.get(username=username)
    assert context.user is not None, f'Expected user "{username}" to exist'


@then('the user "{username}" should have display name "{display_name}"')
def step_user_has_display_name(context, username, display_name):
    user = get_user_model().objects.get(username=username)
    profile = get_user_profile(user)
    assert profile.display_name == display_name, (
        f'Expected user "{username}" to have display name "{display_name}", '
        f'got "{profile.display_name}"'
    )


@then('the user "{username}" should have a usable password "{password}"')
def step_user_has_usable_password(context, username, password):
    user = get_user_model().objects.get(username=username)
    assert user.check_password(password), f'Expected password for "{username}" to validate'


@then('the user "{username}" should have a stored profile picture')
def step_user_has_profile_picture(context, username):
    user = get_user_model().objects.get(username=username)
    profile = get_user_profile(user)
    assert profile.profile_picture.name, f'Expected user "{username}" to have a profile picture'
    assert profile.profile_picture.name.startswith("profile_pictures/"), (
        f'Expected user "{username}" profile picture to be stored under profile_pictures/, '
        f'got "{profile.profile_picture.name}"'
    )


@then('the response should redirect to "{path}"')
def step_response_redirects_to(context, path):
    location = context.response.headers.get("Location", "")
    assert location.endswith(path), f'Expected redirect to "{path}", got "{location}"'


@then('the authenticated user should be "{username}"')
def step_authenticated_user_should_be(context, username):
    expected_user = get_user_model().objects.get(username=username)
    actual_user_id = context.test.client.session.get("_auth_user_id")
    assert str(actual_user_id) == str(expected_user.pk), (
        f'Expected authenticated user id "{expected_user.pk}", got "{actual_user_id}"'
    )
