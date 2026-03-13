import importlib
import os
import shutil
import sys
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import Resolver404, clear_url_caches, resolve, reverse

from .models import UserProfile, get_user_profile
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

    def test_media_urls_are_not_served_when_debug_is_disabled(self):
        with self.settings(DEBUG=False):
            urlconf = self.reload_urlconf()
            with self.assertRaises(Resolver404):
                resolve("/media/profile_pictures/avatar.gif", urlconf=urlconf)

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
            username="quester",
            password="StrongPassword123!",
        )

        self.assertEqual(user.profile.display_name, "quester")
        self.assertEqual(
            user.profile._meta.get_field("profile_picture").upload_to,
            "profile_pictures/",
        )

    def test_string_representation_prefers_display_name(self):
        user = get_user_model().objects.create_user(
            username="quester",
            password="StrongPassword123!",
        )
        user.profile.display_name = "Quest Master"
        user.profile.save()

        self.assertEqual(str(user.profile), "Quest Master")


class AuthenticationFlowTests(TestCase):
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

    def make_profile_picture(self):
        return SimpleUploadedFile(
            "avatar.gif",
            self.TEST_IMAGE_BYTES,
            content_type="image/gif",
        )

    def create_user(
        self,
        username,
        password="StrongPassword123!",
        display_name="Quest Master",
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
        if profile_picture:
            profile.profile_picture = profile_picture
        profile.save()
        return user

    def test_register_creates_user_profile_and_logs_them_in(self):
        response = self.client.post(
            reverse("QuestLog:register"),
            {
                "display_name": "Quest Master",
                "username": "quester",
                "email": "quester@example.com",
                "profile_picture": self.make_profile_picture(),
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            },
        )

        user = get_user_model().objects.get(username="quester")

        self.assertRedirects(response, reverse("QuestLog:profile"))
        self.assertEqual(user.profile.display_name, "Quest Master")
        self.assertEqual(user.email, "quester@example.com")
        self.assertTrue(user.profile.profile_picture.name.startswith("profile_pictures/"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_register_allows_missing_profile_picture(self):
        response = self.client.post(
            reverse("QuestLog:register"),
            {
                "display_name": "Quest Master",
                "username": "quester",
                "email": "quester@example.com",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            },
        )

        user = get_user_model().objects.get(username="quester")

        self.assertRedirects(response, reverse("QuestLog:profile"))
        self.assertEqual(user.profile.display_name, "Quest Master")
        self.assertFalse(user.profile.profile_picture.name)

    def test_login_authenticates_existing_user(self):
        user = self.create_user("quester")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "quester",
                "password": "StrongPassword123!",
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_login_uses_safe_next_redirect(self):
        user = self.create_user("quester")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "quester",
                "password": "StrongPassword123!",
                "next": reverse("QuestLog:tasks"),
            },
        )

        self.assertRedirects(response, reverse("QuestLog:tasks"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_login_allows_redirects_to_configured_hosts(self):
        self.create_user("quester")
        next_url = "https://app.questlog.test/tasks/"

        with self.settings(ALLOWED_HOSTS=["testserver", ".questlog.test"]):
            response = self.client.post(
                reverse("QuestLog:login"),
                {
                    "username": "quester",
                    "password": "StrongPassword123!",
                    "next": next_url,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

    def test_login_rejects_external_redirects(self):
        self.create_user("quester")

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "quester",
                "password": "StrongPassword123!",
                "next": "https://evil.example/phish",
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_login_redirects_authenticated_user_to_profile(self):
        user = self.create_user("quester")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:login"))

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_register_redirects_authenticated_user_to_profile(self):
        user = self.create_user("quester")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:register"))

        self.assertRedirects(response, reverse("QuestLog:profile"))

    def test_profile_page_displays_logged_in_user_details(self):
        user = self.create_user(
            "quester",
            display_name="Quest Master",
            email="quester@example.com",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quest Master")
        self.assertContains(response, "quester")
        self.assertContains(response, "quester@example.com")

    def test_profile_page_handles_missing_profile_picture(self):
        user = self.create_user("quester", display_name="Quest Master")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quest Master")
        self.assertNotContains(response, "profile_pictures/")

    def test_profile_page_recreates_missing_profile_records(self):
        user = self.create_user("quester", display_name="Quest Master")
        user.profile.delete()
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
