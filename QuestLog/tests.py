"""
This file is for all test cases for Django
When you add a new view there should be a test case function added to ViewReachabilityTests class
For testing the deployment there is a DeploymentEnrtypointTests class that will ensure the deployments work
I also added a class SettingsBranchCoverageTests for ensuring the seetings for the project are working as expected
"""

import importlib
import os
import shutil
import sys
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse


class ViewReachabilityTests(TestCase):
    """
    This class is to ensure all views in Django are reachable
    When you create a new view add a function to ensure the endpoint is reachable and returns the correct response code
    """

    def assert_view_status(self, view_name, expected_status=200):
        response = self.client.get(reverse(f"QuestLog:{view_name}"))
        self.assertEqual(response.status_code, expected_status)

    def test_home_view_returns_200(self):
        self.assert_view_status("home", 200)

    def test_about_view_returns_200(self):
        self.assert_view_status("about", 200)

    def test_tasks_view_returns_200(self):
        self.assert_view_status("tasks", 200)

    def test_complete_task_view_returns_200(self):
        self.assert_view_status("complete_task", 200)

    def test_login_view_returns_200(self):
        self.assert_view_status("login", 200)

    def test_register_view_returns_200(self):
        self.assert_view_status("register", 200)

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


class SettingsBranchCoverageTests(TestCase):
    def test_render_hostname_and_whitenoise_branches(self):
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


class UserModelTests(TestCase):
    def test_user_model_is_questlog_user(self):
        user_model = get_user_model()

        self.assertEqual(user_model._meta.label, "QuestLog.User")
        self.assertEqual(
            user_model._meta.get_field("profile_picture").upload_to,
            "profile_pictures/",
        )

    def test_create_user_supports_username_display_name_and_password(self):
        user = get_user_model().objects.create_user(
            username="quester",
            password="StrongPassword123!",
            display_name="Quest Master",
        )

        self.assertEqual(user.username, "quester")
        self.assertEqual(user.display_name, "Quest Master")
        self.assertTrue(user.check_password("StrongPassword123!"))

    def test_string_representation_prefers_display_name(self):
        user = get_user_model()(username="quester", display_name="Quest Master")

        self.assertEqual(str(user), "Quest Master")


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

    def test_register_creates_user_with_profile_picture_and_logs_them_in(self):
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
        self.assertEqual(user.display_name, "Quest Master")
        self.assertEqual(user.email, "quester@example.com")
        self.assertTrue(user.profile_picture.name.startswith("profile_pictures/"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_login_authenticates_existing_user(self):
        user = get_user_model().objects.create_user(
            username="quester",
            password="StrongPassword123!",
            display_name="Quest Master",
        )

        response = self.client.post(
            reverse("QuestLog:login"),
            {
                "username": "quester",
                "password": "StrongPassword123!",
            },
        )

        self.assertRedirects(response, reverse("QuestLog:profile"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_profile_page_displays_logged_in_user_details(self):
        user = get_user_model().objects.create_user(
            username="quester",
            password="StrongPassword123!",
            display_name="Quest Master",
            email="quester@example.com",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quest Master")
        self.assertContains(response, "quester")
        self.assertContains(response, "quester@example.com")
