import importlib
import os
import shutil
import sys
import tempfile
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import clear_url_caches, resolve, reverse
from PIL import Image

from .forms import QuestLogUserCreationForm
from .models import UserProfile, get_user_profile, profile_picture_upload_to
from .urls import urlpatterns


EXPECTED_VIEW_STATUSES = {
    "home": 200,
    "about": 200,
    "tasks": 200,
    "complete_task": 200,
    "login": 200,
    "register": 200,
    "profile": 302,
}


class ViewReachabilityTests(TestCase):
    def assert_view_status(self, view_name, expected_status=200):
        response = self.client.get(reverse(f"QuestLog:{view_name}"))
        self.assertEqual(response.status_code, expected_status)

    def test_all_named_urls_are_accounted_for(self):
        discovered_names = {pattern.name for pattern in urlpatterns if pattern.name}
        self.assertEqual(discovered_names, set(EXPECTED_VIEW_STATUSES))

    def test_all_named_urls_return_expected_status_codes(self):
        for view_name, expected_status in EXPECTED_VIEW_STATUSES.items():
            with self.subTest(view_name=view_name):
                self.assert_view_status(view_name, expected_status)

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("QuestLog:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("QuestLog:login"), response.url)


class DeploymentEntrypointTests(TestCase):
    def test_config_wsgi_exports_application_alias(self):
        module = importlib.import_module("config.wsgi")
        self.assertIsNotNone(module.application)
        self.assertIs(module.QuestLog, module.application)

    def test_config_asgi_exports_application(self):
        module = importlib.import_module("config.asgi")
        self.assertIsNotNone(module.application)

    def test_questlog_wsgi_reexports_application(self):
        module = importlib.import_module("QuestLog.wsgi")
        self.assertIsNotNone(module.application)


class SettingsBranchCoverageTests(SimpleTestCase):
    def test_debug_defaults_to_false_when_unset(self):
        module = importlib.import_module("config.settings")
        original_argv = sys.argv[:]
        original_render = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        original_debug = os.environ.get("DJANGO_DEBUG")

        try:
            os.environ.pop("RENDER_EXTERNAL_HOSTNAME", None)
            os.environ.pop("DJANGO_DEBUG", None)
            sys.argv = ["manage.py", "runserver"]

            reloaded = importlib.reload(module)
            self.assertFalse(reloaded.DEBUG)
            self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", reloaded.MIDDLEWARE)
            self.assertEqual(
                reloaded.STORAGES["staticfiles"]["BACKEND"],
                "whitenoise.storage.CompressedManifestStaticFilesStorage",
            )
        finally:
            if original_render is None:
                os.environ.pop("RENDER_EXTERNAL_HOSTNAME", None)
            else:
                os.environ["RENDER_EXTERNAL_HOSTNAME"] = original_render

            if original_debug is None:
                os.environ.pop("DJANGO_DEBUG", None)
            else:
                os.environ["DJANGO_DEBUG"] = original_debug

            sys.argv = original_argv
            importlib.reload(module)

    def test_explicit_debug_true_uses_dev_static_storage(self):
        module = importlib.import_module("config.settings")
        original_argv = sys.argv[:]
        original_render = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        original_debug = os.environ.get("DJANGO_DEBUG")

        try:
            os.environ.pop("RENDER_EXTERNAL_HOSTNAME", None)
            os.environ["DJANGO_DEBUG"] = "1"
            sys.argv = ["manage.py", "runserver"]

            reloaded = importlib.reload(module)
            self.assertTrue(reloaded.DEBUG)
            self.assertNotIn("whitenoise.middleware.WhiteNoiseMiddleware", reloaded.MIDDLEWARE)
            self.assertEqual(
                reloaded.STORAGES["staticfiles"]["BACKEND"],
                "django.contrib.staticfiles.storage.StaticFilesStorage",
            )
        finally:
            if original_render is None:
                os.environ.pop("RENDER_EXTERNAL_HOSTNAME", None)
            else:
                os.environ["RENDER_EXTERNAL_HOSTNAME"] = original_render

            if original_debug is None:
                os.environ.pop("DJANGO_DEBUG", None)
            else:
                os.environ["DJANGO_DEBUG"] = original_debug

            sys.argv = original_argv
            importlib.reload(module)

    def test_render_hostname_is_added_when_present(self):
        module = importlib.import_module("config.settings")
        original_argv = sys.argv[:]
        original_render = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        original_debug = os.environ.get("DJANGO_DEBUG")

        try:
            os.environ["RENDER_EXTERNAL_HOSTNAME"] = "example.test"
            os.environ["DJANGO_DEBUG"] = "0"
            sys.argv = ["manage.py", "runserver"]

            reloaded = importlib.reload(module)
            self.assertIn("example.test", reloaded.ALLOWED_HOSTS)
            self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", reloaded.MIDDLEWARE)
        finally:
            if original_render is None:
                os.environ.pop("RENDER_EXTERNAL_HOSTNAME", None)
            else:
                os.environ["RENDER_EXTERNAL_HOSTNAME"] = original_render

            if original_debug is None:
                os.environ.pop("DJANGO_DEBUG", None)
            else:
                os.environ["DJANGO_DEBUG"] = original_debug

            sys.argv = original_argv
            importlib.reload(module)


class UrlConfigurationTests(SimpleTestCase):
    def reload_urlconf(self):
        clear_url_caches()
        return importlib.reload(importlib.import_module("config.urls"))

    def test_media_urls_are_served_by_protected_view_when_debug_is_disabled(self):
        with self.settings(DEBUG=False):
            urlconf = self.reload_urlconf()
            match = resolve("/media/profile_pictures/avatar.gif", urlconf=urlconf)
            self.assertEqual(match.url_name, "media")

        self.reload_urlconf()

    def test_media_urls_are_served_when_debug_is_enabled(self):
        with self.settings(DEBUG=True):
            urlconf = self.reload_urlconf()
            match = resolve("/media/profile_pictures/avatar.gif", urlconf=urlconf)
            self.assertIsNotNone(match)

        self.reload_urlconf()


class UserProfileTests(TestCase):
    def test_user_model_stays_on_django_auth_user(self):
        self.assertEqual(get_user_model()._meta.label, "auth.User")

    def test_create_user_creates_profile_with_default_display_name(self):
        user = get_user_model().objects.create_user(
            username="liljit",
            password="6767676767676767",
        )
        generated_path = profile_picture_upload_to(user.profile, "avatar.gif")

        self.assertEqual(user.profile.display_name, "liljit")
        self.assertTrue(generated_path.startswith("profile_pictures/"))
        self.assertTrue(generated_path.endswith(".gif"))
        self.assertNotEqual(generated_path, "profile_pictures/avatar.gif")

    def test_string_representation_prefers_display_name(self):
        user = get_user_model().objects.create_user(
            username="liljit",
            password="6767676767676767",
        )
        user.profile.display_name = "liljitdisplay"
        user.profile.save()

        self.assertEqual(str(user.profile), "liljitdisplay")


class AuthenticationFlowTests(TestCase):
    VALID_PASSWORD = "LilJitsPass67"
    TEST_IMAGE_BYTES = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
        b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
        b"\x00\x02\x02D\x01\x00;"
    )

    def setUp(self):
        self.temp_media_root = tempfile.mkdtemp()
        self.settings_override = self.settings(MEDIA_ROOT=self.temp_media_root)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)

    def reload_urlconf(self):
        clear_url_caches()
        return importlib.reload(importlib.import_module("config.urls"))

    def make_profile_picture(self):
        return SimpleUploadedFile(
            "avatar.gif",
            self.TEST_IMAGE_BYTES,
            content_type="image/gif",
        )

    def make_large_profile_picture(self):
        return SimpleUploadedFile(
            "avatar.gif",
            self.TEST_IMAGE_BYTES + (b"x" * settings.MAX_PROFILE_PICTURE_SIZE),
            content_type="image/gif",
        )

    def make_bmp_profile_picture(self):
        buffer = BytesIO()
        Image.new("RGB", (1, 1), color="red").save(buffer, format="BMP")
        return SimpleUploadedFile(
            "avatar.bmp",
            buffer.getvalue(),
            content_type="image/bmp",
        )

    def create_user(
        self,
        username,
        password=VALID_PASSWORD,
        display_name="liljitdisplay",
        email="",
        profile_picture=None,
    ):
        user = get_user_model().objects.create_user(
            username=username,
            password=password,
            email=email,
        )
        profile = get_user_profile(user)
        profile.display_name = display_name
        if profile_picture is not None:
            profile.profile_picture = profile_picture
        profile.save()
        return user

    def test_register_creates_user_profile_and_logs_them_in(self):
        response = self.client.post(
            reverse("QuestLog:register"),
            {
                "display_name": "liljitdisplay",
                "username": "liljit",
                "email": "liljit@example.com",
                "profile_picture": self.make_profile_picture(),
                "password1": self.VALID_PASSWORD,
                "password2": self.VALID_PASSWORD,
            },
        )

        user = get_user_model().objects.get(username="liljit")
        profile = get_user_profile(user)

        self.assertRedirects(response, reverse("QuestLog:profile"))
        self.assertEqual(profile.display_name, "liljitdisplay")
        self.assertEqual(user.email, "liljit@example.com")
        self.assertTrue(profile.profile_picture.name.startswith("profile_pictures/"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_register_allows_missing_profile_picture(self):
        response = self.client.post(
            reverse("QuestLog:register"),
            {
                "display_name": "liljitdisplay",
                "username": "liljit",
                "email": "liljit@example.com",
                "password1": self.VALID_PASSWORD,
                "password2": self.VALID_PASSWORD,
            },
        )

        user = get_user_model().objects.get(username="liljit")
        profile = get_user_profile(user)

        self.assertRedirects(response, reverse("QuestLog:profile"))
        self.assertEqual(profile.display_name, "liljitdisplay")
        self.assertFalse(profile.profile_picture.name)

    def test_login_authenticates_existing_user(self):
        user = self.create_user("liljit")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "liljit",
                "password": self.VALID_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_login_uses_safe_next_redirect(self):
        user = self.create_user("liljit")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "liljit",
                "password": self.VALID_PASSWORD,
                "next": reverse("QuestLog:tasks"),
            },
        )

        self.assertRedirects(response, reverse("QuestLog:tasks"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_login_allows_redirects_to_configured_hosts(self):
        self.create_user("liljit")
        next_url = "https://app.questlog.test/tasks/"

        with self.settings(
            ALLOWED_HOSTS=["testserver"],
            REDIRECT_ALLOWED_HOSTS=["app.questlog.test"],
        ):
            response = self.client.post(
                reverse("QuestLog:login"),
                {
                    "username": "liljit",
                    "password": self.VALID_PASSWORD,
                    "next": next_url,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

    def test_login_rejects_absolute_redirects_when_allowed_hosts_is_wildcard(self):
        self.create_user("liljit")

        with self.settings(ALLOWED_HOSTS=["*"], REDIRECT_ALLOWED_HOSTS=[]):
            response = self.client.post(
                reverse("QuestLog:login"),
                {
                    "username": "liljit",
                    "password": self.VALID_PASSWORD,
                    "next": "https://attacker.com/phish",
                },
            )

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_login_rejects_external_redirects(self):
        self.create_user("liljit")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "liljit",
                "password": self.VALID_PASSWORD,
                "next": "https://evil.example/phish",
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_login_rejects_invalid_redirect_schemes(self):
        self.create_user("liljit")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "liljit",
                "password": self.VALID_PASSWORD,
                "next": "javascript:alert('xss')",
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_login_rejects_scheme_relative_redirects(self):
        self.create_user("liljit")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "liljit",
                "password": self.VALID_PASSWORD,
                "next": "//evil.com/phish",
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_login_rejects_backslash_prefixed_redirects(self):
        self.create_user("liljit")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "liljit",
                "password": self.VALID_PASSWORD,
                "next": "/\\\\evil",
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_login_redirects_authenticated_user_to_profile(self):
        user = self.create_user("liljit")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:login"))

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_register_redirects_authenticated_user_to_profile(self):
        user = self.create_user("liljit")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:register"))

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_profile_page_displays_logged_in_user_details(self):
        user = self.create_user(
            "liljit",
            display_name="liljitdisplay",
            email="liljit@example.com",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "liljitdisplay")
        self.assertContains(response, "liljit")
        self.assertContains(response, "liljit@example.com")

    def test_profile_page_handles_missing_profile_picture(self):
        user = self.create_user("liljit", display_name="liljitdisplay")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "liljitdisplay")
        self.assertNotContains(response, "profile_pictures/")

    def test_profile_page_recreates_missing_profile_records(self):
        user = self.create_user("liljit", display_name="liljitdisplay")
        user.profile.delete()
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_production_media_requires_authentication(self):
        user = self.create_user("liljit", profile_picture=self.make_profile_picture())
        profile = get_user_profile(user)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(profile.profile_picture.url)

        self.assertRedirects(
            response,
            f"{reverse('QuestLog:login')}?next={profile.profile_picture.url}",
        )
        self.reload_urlconf()

    def test_production_media_serves_profile_picture_for_authenticated_user(self):
        user = self.create_user("liljit", profile_picture=self.make_profile_picture())
        profile = get_user_profile(user)
        self.client.force_login(user)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(profile.profile_picture.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.TEST_IMAGE_BYTES)
        self.reload_urlconf()

    def test_production_media_rejects_other_users_profile_pictures(self):
        owner = self.create_user("liljit", profile_picture=self.make_profile_picture())
        intruder = self.create_user("otherliljit")
        owner_profile = get_user_profile(owner)
        self.client.force_login(intruder)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(owner_profile.profile_picture.url)

        self.assertEqual(response.status_code, 404)
        self.reload_urlconf()

    def test_production_media_rejects_case_changed_profile_picture_paths(self):
        user = self.create_user("liljit", profile_picture=self.make_profile_picture())
        profile = get_user_profile(user)
        self.client.force_login(user)

        altered_url = f"/media/{profile.profile_picture.name.upper()}"

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(altered_url)

        self.assertEqual(response.status_code, 404)
        self.reload_urlconf()

    def test_production_media_rejects_path_traversal(self):
        user = self.create_user("liljit")
        self.client.force_login(user)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get("/media/../config/settings.py")

        self.assertEqual(response.status_code, 404)
        self.reload_urlconf()

    def test_user_creation_form_save_commit_false_creates_profile_on_save(self):
        form = QuestLogUserCreationForm(
            data={
                "display_name": "liljitdisplay",
                "username": "liljit",
                "email": "liljit@example.com",
                "password1": self.VALID_PASSWORD,
                "password2": self.VALID_PASSWORD,
            },
            files={"profile_picture": self.make_profile_picture()},
        )

        self.assertTrue(form.is_valid(), form.errors)

        user = form.save(commit=False)
        self.assertIsNone(user.pk)
        self.assertFalse(hasattr(user, "_questlog_profile_data"))
        user.save()
        form.save_profile(user)
        profile = get_user_profile(user)

        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(profile.display_name, "liljitdisplay")
        self.assertTrue(profile.profile_picture.name.startswith("profile_pictures/"))

    def test_user_creation_form_rejects_large_profile_pictures(self):
        form = QuestLogUserCreationForm(
            data={
                "display_name": "liljitdisplay",
                "username": "liljit",
                "email": "liljit@example.com",
                "password1": self.VALID_PASSWORD,
                "password2": self.VALID_PASSWORD,
            },
            files={"profile_picture": self.make_large_profile_picture()},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Profile pictures must be 5 MB or smaller.", form.errors["profile_picture"])

    def test_user_creation_form_rejects_unsupported_profile_picture_content_types(self):
        form = QuestLogUserCreationForm(
            data={
                "display_name": "liljitdisplay",
                "username": "liljit",
                "email": "liljit@example.com",
                "password1": self.VALID_PASSWORD,
                "password2": self.VALID_PASSWORD,
            },
            files={
                "profile_picture": self.make_bmp_profile_picture()
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Unsupported profile picture file type.", form.errors["profile_picture"])
