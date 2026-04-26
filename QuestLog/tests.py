import importlib
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import clear_url_caches, resolve, reverse
from PIL import Image

from .forms import CreateTaskForm, QuestLogUserCreationForm
from .models import Party, PartyInvitation, Reward, Task, TaskDifficultyVote, UserPoints, UserProfile, get_user_profile, profile_picture_upload_to
from .urls import urlpatterns

import json

EXPECTED_VIEW_GET_STATUSES = {
    "home": 200,
    "about": 200,
    "tasks": 200,
    "task_history": 200,
    "complete_task": 302,
    "create_task": 302,
    "login": 200,
    "logout": 302,
    "register": 200,
    "profile": 302,
    'parties': 302,
    'party_details': 302,
    'leaderboard': 302,
    'upload_task_proof': 405,
    'create_party': 302,
}

EXPECTED_VIEW_POST_STATUSES = {
    "profile": 302,
    'upload_task_proof': 302,
}


class ViewReachabilityTests(TestCase):
    def assert_view_get_status(self, view_name, expected_status=200):
        response = self.client.get(reverse(f"QuestLog:{view_name}"))
        self.assertEqual(response.status_code, expected_status)

    def assert_view_post_status(self, view_name, expected_status=200):
        response = self.client.post(reverse(f"QuestLog:{view_name}"))
        self.assertEqual(response.status_code, expected_status)

    def test_all_named_urls_are_accounted_for(self):
        discovered_names = {pattern.name for pattern in urlpatterns if pattern.name}
        
        # routes with required path parameters are tested separately
        ignored_names = { "accept_party_invitation", "decline_party_invitation", "vote_task_difficulty" }
        
        self.assertEqual(discovered_names - ignored_names, set(EXPECTED_VIEW_GET_STATUSES))

    def test_all_named_urls_return_expected_status_codes(self):
        #get statuses when not signed in
        for view_name, expected_status in EXPECTED_VIEW_GET_STATUSES.items():
            with self.subTest(view_name=view_name):
                self.assert_view_get_status(view_name, expected_status)
        #post statuses when not signed in
        for view_name, expected_status in EXPECTED_VIEW_POST_STATUSES.items():
            with self.subTest(view_name=view_name):
                self.assert_view_post_status(view_name, expected_status)

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
            os.environ.pop("DJANGO_DEBUG", None)
            os.environ["RENDER_EXTERNAL_HOSTNAME"] = "example.com"
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
        self.assertEqual(get_user_model()._meta.label, settings.AUTH_USER_MODEL)

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

    def test_profile_post_all_entries(self):
        user = AuthenticationFlowTests.create_user(AuthenticationFlowTests, "liljit")
        self.client.force_login(user)
        resp = self.client.post(reverse(f"QuestLog:profile"), json.dumps({"display_name": "testname", "email": "test3@example.com", }), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(get_user_profile(user).display_name, "testname")
        user = get_user_model().objects.get(pk=user.pk)
        self.assertEqual(user.email, "test3@example.com")

    def test_profile_post_partial_entries(self):
        user = AuthenticationFlowTests.create_user(AuthenticationFlowTests, "liljit")
        self.client.force_login(user)
        resp = self.client.post(reverse(f"QuestLog:profile"), json.dumps({"display_name": "testname"}), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(get_user_profile(user).display_name, "testname")

    def test_profile_post_bad(self):
        user = AuthenticationFlowTests.create_user(AuthenticationFlowTests, "liljit")
        self.client.force_login(user)
        resp = self.client.post(reverse(f"QuestLog:profile"), json.dumps({"ghjghkjghj": "testname"}), content_type="application/json")
        self.assertEqual(resp.status_code, 400)


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

    @contextmanager
    def without_profile_picture_settings(self):
        wrapped_settings = settings._wrapped
        sentinel = object()
        originals = {}
        setting_names = ("MAX_PROFILE_PICTURE_SIZE", "ALLOWED_PROFILE_PICTURE_FORMATS")

        for setting_name in setting_names:
            originals[setting_name] = getattr(wrapped_settings, setting_name, sentinel)
            if originals[setting_name] is not sentinel:
                delattr(wrapped_settings, setting_name)

        try:
            yield
        finally:
            for setting_name, original_value in originals.items():
                if original_value is sentinel:
                    if hasattr(wrapped_settings, setting_name):
                        delattr(wrapped_settings, setting_name)
                else:
                    setattr(wrapped_settings, setting_name, original_value)

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

    def make_task_proof(self):
        return SimpleUploadedFile(
            "proof.gif",
            self.TEST_IMAGE_BYTES,
            content_type="image/gif",
        )

    def create_user(
        self,
        username,
        password=VALID_PASSWORD,
        display_name="liljitdisplay",
        email="user@example.com",
        profile_picture=None,
    ):# params to this function are multiline

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
        return user #returns a instance of djangos built in user model

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

        self.assertRedirects(response, reverse("QuestLog:home"))
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

        self.assertRedirects(response, reverse("QuestLog:home"))
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

        self.assertRedirects(response, reverse("QuestLog:home"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))


    def test_logout_logs_out(self):
        user = self.create_user("liljit")
        self.client.force_login(user)
        resp1 = self.client.get(reverse("QuestLog:profile"))
        resp2 = self.client.get(reverse("QuestLog:logout"))
        resp3 = self.client.get(reverse("QuestLog:profile"))
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 302)#logout
        self.assertEqual(resp3.status_code, 302)


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
                secure=True,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

    def test_login_allows_same_host_absolute_http_redirects_on_insecure_requests(self):
        user = self.create_user("liljit")
        next_url = "http://testserver/tasks/"

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
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_login_rejects_insecure_redirects_to_configured_hosts(self):
        self.create_user("liljit")

        with self.settings(
            ALLOWED_HOSTS=["testserver"],
            REDIRECT_ALLOWED_HOSTS=["app.questlog.test"],
        ):
            response = self.client.post(
                reverse("QuestLog:login"),
                {
                    "username": "liljit",
                    "password": self.VALID_PASSWORD,
                    "next": "http://app.questlog.test/tasks/",
                },
            )

        self.assertRedirects(response, reverse("QuestLog:home"))

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

        self.assertRedirects(response, reverse("QuestLog:home"))

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

        self.assertRedirects(response, reverse("QuestLog:home"))

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

        self.assertRedirects(response, reverse("QuestLog:home"))

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

        self.assertRedirects(response, reverse("QuestLog:home"))

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

        self.assertRedirects(response, reverse("QuestLog:home"))

    def test_login_redirects_authenticated_user_to_profile(self):
        user = self.create_user("liljit")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:login"))

        self.assertRedirects(response, reverse("QuestLog:home"))

    def test_register_redirects_authenticated_user_to_profile(self):
        user = self.create_user("liljit")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:register"))

        self.assertRedirects(response, reverse("QuestLog:home"))

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

    def test_production_media_serves_profile_picture_for_other_authenticated_users(self):
        owner = self.create_user("liljit", profile_picture=self.make_profile_picture())
        intruder = self.create_user("otherliljit")
        owner_profile = get_user_profile(owner)
        self.client.force_login(intruder)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(owner_profile.profile_picture.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.TEST_IMAGE_BYTES)
        self.reload_urlconf()

    def test_production_media_rejects_orphaned_profile_picture_files(self):
        os.makedirs(os.path.join(self.temp_media_root, "profile_pictures"), exist_ok=True)
        orphan_path = os.path.join(self.temp_media_root, "profile_pictures", "orphan.gif")
        with open(orphan_path, "wb") as orphan_file:
            orphan_file.write(self.TEST_IMAGE_BYTES)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get("/media/profile_pictures/orphan.gif")

        self.assertEqual(response.status_code, 404)
        self.reload_urlconf()

    def test_production_media_rejects_non_profile_picture_directories(self):
        user = self.create_user("liljit")
        profile = get_user_profile(user)
        os.makedirs(os.path.join(self.temp_media_root, "some_other_dir"), exist_ok=True)
        secret_path = os.path.join(self.temp_media_root, "some_other_dir", "secret.txt")
        with open(secret_path, "wb") as secret_file:
            secret_file.write(b"private")

        profile.profile_picture.name = "some_other_dir/secret.txt"
        profile.save(update_fields=["profile_picture"])

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get("/media/some_other_dir/secret.txt")

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

    def test_production_media_rejects_task_proof_for_anonymous_users(self):
        owner = self.create_user("proofowner")
        party = Party.objects.create(party_name="Proof Party", creator=owner)
        party.members.add(owner)
        task = Task.objects.create(
            owner=owner,
            name="Secret Proof Task",
            description="Proof should not be public.",
            affiliation=party,
            proofs=self.make_task_proof(),
            status=Task.Status.COMPLETED,
        )

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(task.proofs.url)

        self.assertEqual(response.status_code, 404)
        self.reload_urlconf()

    def test_production_media_rejects_task_proof_for_non_party_members(self):
        owner = self.create_user("proofowner")
        intruder = self.create_user("proofintruder")
        party = Party.objects.create(party_name="Proof Party", creator=owner)
        party.members.add(owner)
        task = Task.objects.create(
            owner=owner,
            name="Secret Proof Task",
            description="Proof should not be public.",
            affiliation=party,
            proofs=self.make_task_proof(),
            status=Task.Status.COMPLETED,
        )
        self.client.force_login(intruder)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(task.proofs.url)

        self.assertEqual(response.status_code, 404)
        self.reload_urlconf()

    def test_production_media_serves_task_proof_for_party_members(self):
        owner = self.create_user("proofowner")
        member = self.create_user("proofmember")
        party = Party.objects.create(party_name="Proof Party", creator=owner)
        party.members.add(owner, member)
        task = Task.objects.create(
            owner=owner,
            name="Secret Proof Task",
            description="Proof should be visible to party members.",
            affiliation=party,
            proofs=self.make_task_proof(),
            status=Task.Status.COMPLETED,
        )
        self.client.force_login(member)

        with self.settings(DEBUG=False):
            self.reload_urlconf()
            response = self.client.get(task.proofs.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.TEST_IMAGE_BYTES)
        self.reload_urlconf()

    def test_complete_task_rejects_non_numeric_task_id(self):
        user = self.create_user("taskviewer")
        self.client.force_login(user)

        response = self.client.get(reverse("QuestLog:complete_task"), {"task_id": "abc"})

        self.assertRedirects(response, reverse("QuestLog:tasks"))

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

    def test_user_creation_form_uses_defaults_when_profile_picture_settings_are_missing(self):
        with self.without_profile_picture_settings():
            form = QuestLogUserCreationForm(
                data={
                    "display_name": "liljitdisplay",
                    "username": "fallbackuser",
                    "email": "fallback@example.com",
                    "password1": self.VALID_PASSWORD,
                    "password2": self.VALID_PASSWORD,
                },
                files={"profile_picture": self.make_profile_picture()},
            )

            self.assertTrue(form.is_valid(), form.errors)

    def test_user_creation_form_rejects_non_image_payloads_with_image_content_types(self):
        form = QuestLogUserCreationForm(
            data={
                "display_name": "liljitdisplay",
                "username": "notanimage",
                "email": "notanimage@example.com",
                "password1": self.VALID_PASSWORD,
                "password2": self.VALID_PASSWORD,
            },
            files={
                "profile_picture": SimpleUploadedFile(
                    "avatar.png",
                    b"this is not a real image",
                    content_type="image/png",
                )
            },
        )

        self.assertFalse(form.is_valid())
        self.assertTrue(
            any("Upload a valid image" in error for error in form.errors["profile_picture"])
        )


class PartyViewsTemplateTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from .models import Party

        User = get_user_model()
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="test-password",
        )
        self.party = Party.objects.create(
            party_name="Test Party",
            creator=self.user,
        )
        self.party.members.add(self.user)


class TaskPagesTemplateTests(TestCase):
    TEST_IMAGE_BYTES = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
        b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
        b"\x00\x02\x02D\x01\x00;"
    )

    def setUp(self):
        from .models import Party, Task

        self.Task = Task
        self.user = get_user_model().objects.create_user(
            username="taskuser",
            email="taskuser@example.com",
            password="test-password",
        )
        self.other_user = get_user_model().objects.create_user(
            username="othertaskuser",
            email="othertaskuser@example.com",
            password="test-password",
        )
        self.party = Party.objects.create(
            party_name="Task Party",
            creator=self.user,
        )
        self.party.members.add(self.user, self.other_user)

        self.active_task = Task.objects.create(
            owner=self.user,
            name="Open Item",
            description="This should appear on tasks page only.",
            status=Task.Status.NOT_STARTED,
            point_value=5,
            affiliation=self.party,
        )
        self.completed_task = Task.objects.create(
            owner=self.user,
            name="Done Item",
            description="This should appear on task history only.",
            status=Task.Status.COMPLETED,
            point_value=10,
            affiliation=self.party,
            proofs=SimpleUploadedFile(
                "proof.gif",
                self.TEST_IMAGE_BYTES,
                content_type="image/gif",
            ),
        )
        self.other_users_completed_task = Task.objects.create(
            owner=self.other_user,
            name="Other User Done Item",
            description="Should not appear for logged in user.",
            status=Task.Status.COMPLETED,
            point_value=15,
            affiliation=self.party,
        )

        self.client.force_login(self.user)

    def test_tasks_view_shows_only_incomplete_tasks_for_logged_in_user(self):
        response = self.client.get(reverse("QuestLog:tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tasks.html")
        self.assertContains(response, "Open Item")
        self.assertNotContains(response, "Done Item")
        self.assertContains(response, reverse("QuestLog:task_history"))

    def test_task_history_view_shows_only_completed_tasks_for_logged_in_user(self):
        response = self.client.get(reverse("QuestLog:task_history"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tasks_history.html")
        self.assertContains(response, "Done Item")
        self.assertNotContains(response, "Open Item")
        self.assertNotContains(response, "Other User Done Item")
        self.assertContains(response, self.completed_task.proofs.url)
        self.assertContains(response, reverse("QuestLog:tasks"))
        self.assertNotContains(response, "Accept")

class LeaderboardViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.db import IntegrityError

        from .models import Party, Reward, UserPoints, get_user_profile

        self.IntegrityError = IntegrityError
        User = get_user_model()

        self.user1 = User.objects.create_user(
            username="lilpump",
            email="lilpump@example.com",
            password="test-password",
        )
        self.user2 = User.objects.create_user(
            username="lilpeep",
            email="lilpeep@example.com",
            password="test-password",
        )
        self.user3 = User.objects.create_user(
            username="lilyatchy",
            email="lilyatchy@example.com",
            password="test-password",
        )

        profile1 = get_user_profile(self.user1)
        profile1.display_name = "lilpump"
        profile1.save()

        profile2 = get_user_profile(self.user2)
        profile2.display_name = "lilpeep"
        profile2.save()

        profile3 = get_user_profile(self.user3)
        profile3.display_name = "lilyatchy"
        profile3.save()

        self.party1 = Party.objects.create(
            party_name="Red Team",
            creator=self.user1,
        )
        self.party2 = Party.objects.create(
            party_name="Blue Team",
            creator=self.user1,
        )

        self.party1.members.add(self.user1, self.user2)
        self.party2.members.add(self.user1, self.user3)

        self.reward = Reward.objects.create(class_attributes="Default Reward")

        self.user1_red_points = UserPoints.objects.create(
            user=self.user1,
            party=self.party1,
            points=50,
            rewards=self.reward,
        )
        self.user2_red_points = UserPoints.objects.create(
            user=self.user2,
            party=self.party1,
            points=80,
            rewards=self.reward,
        )
        self.user1_blue_points = UserPoints.objects.create(
            user=self.user1,
            party=self.party2,
            points=25,
            rewards=self.reward,
        )
        self.user3_blue_points = UserPoints.objects.create(
            user=self.user3,
            party=self.party2,
            points=60,
            rewards=self.reward,
        )

    def test_leaderboard_requires_authentication(self):
        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("QuestLog:login"), response.url)

    def test_leaderboard_uses_template(self):
        self.client.force_login(self.user1)

        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "leaderboard.html")

    def test_leaderboard_shows_empty_state_for_user_with_no_parties(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        no_party_user = User.objects.create_user(
            username="nobody",
            email="nobody@example.com",
            password="test-password",
        )

        self.client.force_login(no_party_user)
        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No parties yet")
        self.assertContains(response, "Create / join a party")

    def test_leaderboard_shows_only_logged_in_users_parties(self):
        self.client.force_login(self.user2)

        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Red Team")
        self.assertNotContains(response, "Blue Team")

    def test_leaderboard_context_contains_parties_for_logged_in_user(self):
        self.client.force_login(self.user1)

        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("party_leaderboards", response.context)
        self.assertEqual(len(response.context["party_leaderboards"]), 2)
        self.assertEqual(response.context["party_leaderboards"][0]["party"], self.party2)
        self.assertEqual(response.context["party_leaderboards"][1]["party"], self.party1)

    def test_leaderboard_orders_scores_descending_within_each_party(self):
        self.client.force_login(self.user1)

        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 200)

        party_leaderboards = response.context["party_leaderboards"]

        blue_team_standings = list(party_leaderboards[0]["standings"])
        red_team_standings = list(party_leaderboards[1]["standings"])

        self.assertEqual(blue_team_standings[0].user, self.user3)
        self.assertEqual(blue_team_standings[1].user, self.user1)

        self.assertEqual(red_team_standings[0].user, self.user2)
        self.assertEqual(red_team_standings[1].user, self.user1)

    def test_leaderboard_displays_member_display_names(self):
        self.client.force_login(self.user1)

        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lilpump")
        self.assertContains(response, "lilpeep")
        self.assertContains(response, "lilyatchy")

    def test_leaderboard_marks_logged_in_user_as_you(self):
        self.client.force_login(self.user1)

        response = self.client.get(reverse("QuestLog:leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You")

    def test_userpoints_is_unique_per_user_and_party(self):
        with self.assertRaises(self.IntegrityError):
            self.user1_red_points.__class__.objects.create(
                user=self.user1,
                party=self.party1,
                points=999,
                rewards=self.reward,
            )
    
    def test_anonymous_user_does_not_see_leaderboard_link(self):
        response = self.client.get(reverse("QuestLog:home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("QuestLog:leaderboard"))

    def test_authenticated_user_sees_leaderboard_link(self):
        self.client.force_login(self.user1)
        response = self.client.get(reverse("QuestLog:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("QuestLog:leaderboard"))


class TaskWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.creator = User.objects.create_user(
            username="taskowner",
            email="taskowner@example.com",
            password="test-password",
        )
        self.party_member = User.objects.create_user(
            username="partymember",
            email="member@example.com",
            password="test-password",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="test-password",
        )

        get_user_profile(self.creator)
        get_user_profile(self.party_member)
        get_user_profile(self.outsider)

        self.party = Party.objects.create(
            party_name="Quest Makers",
            creator=self.creator,
        )
        self.party.members.add(self.creator, self.party_member)

    def test_create_task_requires_authentication(self):
        response = self.client.get(reverse("QuestLog:create_task"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("QuestLog:login"), response.url)

    def test_authenticated_member_can_view_create_task_page(self):
        self.client.force_login(self.creator)

        response = self.client.get(
            reverse("QuestLog:create_task"),
            {"guid": str(self.party.guid)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "create_task.html")
        self.assertEqual(response.context["selected_party"], self.party)

    def test_create_task_form_uses_party_name_for_affiliation_label(self):
        form = CreateTaskForm(user=self.creator)
        affiliation_field = form.fields["affiliation"]

        self.assertEqual(affiliation_field.label_from_instance(self.party), "Quest Makers")

    def test_create_task_post_creates_task_and_initial_vote(self):
        self.client.force_login(self.creator)

        response = self.client.post(
            reverse("QuestLog:create_task") + f"?guid={self.party.guid}",
            {
                "guid": str(self.party.guid),
                "affiliation": self.party.id,
                "name": "Clean the guild hall",
                "description": "Sweep the floors and reset the tables after raid night.",
                "difficulty_rating": 4,
                "recurring": 0,
            },
        )

        task = Task.objects.get(name="Clean the guild hall")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(task.affiliation, self.party)
        self.assertEqual(task.owner, self.creator)
        self.assertEqual(task.difficulty_rating, 4)
        self.assertEqual(task.point_value, 40)
        self.assertTrue(
            TaskDifficultyVote.objects.filter(
                task=task,
                voter=self.creator,
                rating=4,
            ).exists()
        )

    def test_tasks_view_shows_add_task_link_for_selected_party(self):
        self.client.force_login(self.creator)

        response = self.client.get(
            reverse("QuestLog:tasks"),
            {"guid": str(self.party.guid)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("QuestLog:create_task") + f"?guid={self.party.guid}",
        )

    def test_party_member_can_vote_on_task_difficulty(self):
        task = Task.objects.create(
            owner=self.creator,
            affiliation=self.party,
            name="Restock supplies",
            description="Refill potions, rope, and torches.",
            difficulty_rating=2,
            point_value=2,
        )
        TaskDifficultyVote.objects.create(
            task=task,
            voter=self.creator,
            rating=2,
        )

        self.client.force_login(self.party_member)
        response = self.client.post(
            reverse("QuestLog:vote_task_difficulty", args=[task.id]),
            {"rating": 4},
        )

        task.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TaskDifficultyVote.objects.filter(
                task=task,
                voter=self.party_member,
                rating=4,
            ).exists()
        )
        self.assertAlmostEqual(task.weighted_difficulty, 3.0)

    def test_non_member_cannot_vote_on_task_difficulty(self):
        task = Task.objects.create(
            owner=self.creator,
            affiliation=self.party,
            name="Scout the perimeter",
            description="Walk the outer wall and mark weak points.",
            difficulty_rating=3,
            point_value=3,
        )
        TaskDifficultyVote.objects.create(
            task=task,
            voter=self.creator,
            rating=3,
        )

        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("QuestLog:vote_task_difficulty", args=[task.id]),
            {"rating": 5},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            TaskDifficultyVote.objects.filter(
                task=task,
                voter=self.outsider,
            ).exists()
        )

class PartyInvitationWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()

        # create users for party workflow testing
        self.creator = User.objects.create_user(
            username="partycreator",
            email="creator@example.com",
            password="test-password",
        )
        self.invited_user = User.objects.create_user(
            username="inviteduser",
            email="invited@example.com",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="test-password",
        )

        # create profiles so display-related pages have expected data
        get_user_profile(self.creator)
        get_user_profile(self.invited_user)
        get_user_profile(self.other_user)

        # reward used for userpoints creation
        self.reward = Reward.objects.create(class_attributes="Default Reward")

    def test_create_party_requires_authentication(self):
        response = self.client.get(reverse("QuestLog:create_party"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("QuestLog:login"), response.url)

    def test_authenticated_user_can_view_create_party_page(self):
        self.client.force_login(self.creator)

        response = self.client.get(reverse("QuestLog:create_party"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "create_party.html")

    def test_create_party_post_creates_party_and_adds_creator_as_member(self):
        self.client.force_login(self.creator)

        response = self.client.post(
            reverse("QuestLog:create_party"),
            {
                "party_name": "A Team",
                "invited_username": "",
            },
        )

        self.assertEqual(response.status_code, 302)

        party = Party.objects.get(party_name="A Team")
        self.assertEqual(party.creator, self.creator)
        self.assertTrue(party.members.filter(pk=self.creator.pk).exists())

    def test_create_party_post_creates_userpoints_for_creator(self):
        self.client.force_login(self.creator)

        self.client.post(
            reverse("QuestLog:create_party"),
            {
                "party_name": "B Team",
                "invited_username": "",
            },
        )

        party = Party.objects.get(party_name="B Team")
        self.assertTrue(
            UserPoints.objects.filter(user=self.creator, party=party).exists()
        )

    def test_create_party_with_valid_invited_username_creates_pending_invitation(self):
        self.client.force_login(self.creator)

        self.client.post(
            reverse("QuestLog:create_party"),
            {
                "party_name": "C Team",
                "invited_username": "inviteduser",
            },
        )

        party = Party.objects.get(party_name="C Team")
        invitation = PartyInvitation.objects.get(
            party=party,
            invited_user=self.invited_user,
        )

        self.assertEqual(invitation.invited_by, self.creator)
        self.assertEqual(invitation.status, PartyInvitation.Status.PENDING)

    def test_create_party_with_unknown_username_still_creates_party(self):
        self.client.force_login(self.creator)

        response = self.client.post(
            reverse("QuestLog:create_party"),
            {
                "party_name": "D Team",
                "invited_username": "notarealuser",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Party.objects.filter(party_name="D Team").exists())
        self.assertEqual(PartyInvitation.objects.count(), 0)

    def test_party_details_requires_logged_in_member(self):
        party = Party.objects.create(
            party_name="Private Party",
            creator=self.creator,
        )
        party.members.add(self.creator)

        response = self.client.get(
            reverse("QuestLog:party_details"),
            {"guid": str(party.guid)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("QuestLog:login"), response.url)

    def test_party_details_rejects_non_member(self):
        party = Party.objects.create(
            party_name="Members Only",
            creator=self.creator,
        )
        party.members.add(self.creator)

        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("QuestLog:party_details"),
            {"guid": str(party.guid)},
        )

        self.assertEqual(response.status_code, 302)

    def test_party_details_allows_member_and_uses_template(self):
        party = Party.objects.create(
            party_name="Adventure Party",
            creator=self.creator,
        )
        party.members.add(self.creator)

        self.client.force_login(self.creator)
        response = self.client.get(
            reverse("QuestLog:party_details"),
            {"guid": str(party.guid)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "party_details.html")
        self.assertEqual(response.context["party"], party)

    def test_party_details_post_invites_valid_user(self):
        party = Party.objects.create(
            party_name="Invite Test Party",
            creator=self.creator,
        )
        party.members.add(self.creator)

        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("QuestLog:party_details") + f"?guid={party.guid}",
            {
                "username": "inviteduser",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            PartyInvitation.objects.filter(
                party=party,
                invited_user=self.invited_user,
                invited_by=self.creator,
                status=PartyInvitation.Status.PENDING,
            ).exists()
        )

    def test_party_details_post_rejects_inviting_yourself(self):
        party = Party.objects.create(
            party_name="Self Invite Test",
            creator=self.creator,
        )
        party.members.add(self.creator)

        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("QuestLog:party_details") + f"?guid={party.guid}",
            {
                "username": "partycreator",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PartyInvitation.objects.filter(
                party=party,
                invited_user=self.creator,
            ).exists()
        )

    def test_party_details_post_rejects_existing_member(self):
        party = Party.objects.create(
            party_name="Existing Member Test",
            creator=self.creator,
        )
        party.members.add(self.creator, self.invited_user)

        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("QuestLog:party_details") + f"?guid={party.guid}",
            {
                "username": "inviteduser",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PartyInvitation.objects.filter(
                party=party,
                invited_user=self.invited_user,
            ).exists()
        )

    def test_accept_party_invitation_adds_user_to_party(self):
        party = Party.objects.create(
            party_name="Accept Invite Party",
            creator=self.creator,
        )
        party.members.add(self.creator)

        invitation = PartyInvitation.objects.create(
            party=party,
            invited_user=self.invited_user,
            invited_by=self.creator,
            status=PartyInvitation.Status.PENDING,
        )

        self.client.force_login(self.invited_user)
        response = self.client.post(
            reverse("QuestLog:accept_party_invitation", args=[invitation.id])
        )

        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(party.members.filter(pk=self.invited_user.pk).exists())
        self.assertEqual(invitation.status, PartyInvitation.Status.ACCEPTED)

    def test_accept_party_invitation_creates_userpoints_for_invited_user(self):
        party = Party.objects.create(
            party_name="Points On Accept",
            creator=self.creator,
        )
        party.members.add(self.creator)

        invitation = PartyInvitation.objects.create(
            party=party,
            invited_user=self.invited_user,
            invited_by=self.creator,
            status=PartyInvitation.Status.PENDING,
        )

        self.client.force_login(self.invited_user)
        self.client.post(reverse("QuestLog:accept_party_invitation", args=[invitation.id]))

        self.assertTrue(
            UserPoints.objects.filter(
                user=self.invited_user,
                party=party,
            ).exists()
        )

    def test_decline_party_invitation_updates_status_and_does_not_add_member(self):
        party = Party.objects.create(
            party_name="Decline Invite Party",
            creator=self.creator,
        )
        party.members.add(self.creator)

        invitation = PartyInvitation.objects.create(
            party=party,
            invited_user=self.invited_user,
            invited_by=self.creator,
            status=PartyInvitation.Status.PENDING,
        )

        self.client.force_login(self.invited_user)
        response = self.client.post(
            reverse("QuestLog:decline_party_invitation", args=[invitation.id])
        )

        invitation.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(invitation.status, PartyInvitation.Status.DECLINED)
        self.assertFalse(party.members.filter(pk=self.invited_user.pk).exists())

    def test_user_cannot_accept_someone_elses_invitation(self):
        party = Party.objects.create(
            party_name="Wrong User Test",
            creator=self.creator,
        )
        party.members.add(self.creator)

        invitation = PartyInvitation.objects.create(
            party=party,
            invited_user=self.invited_user,
            invited_by=self.creator,
            status=PartyInvitation.Status.PENDING,
        )

        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("QuestLog:accept_party_invitation", args=[invitation.id])
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(party.members.filter(pk=self.other_user.pk).exists())

    def test_profile_page_shows_pending_party_invitations(self):
        party = Party.objects.create(
            party_name="Profile Invite Party",
            creator=self.creator,
        )
        party.members.add(self.creator)

        PartyInvitation.objects.create(
            party=party,
            invited_user=self.invited_user,
            invited_by=self.creator,
            status=PartyInvitation.Status.PENDING,
        )

        self.client.force_login(self.invited_user)
        response = self.client.get(reverse("QuestLog:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Party Invitations")
        self.assertContains(response, "Profile Invite Party")
        self.assertContains(response, "Accept")
        self.assertContains(response, "Decline")

class TaskDifficultyAndRecurringTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="difficultyuser",
            email="difficultyuser@example.com",
            password="test-password",
        )
        self.other_user = get_user_model().objects.create_user(
            username="difficultyfriend",
            email="difficultyfriend@example.com",
            password="test-password",
        )

        get_user_profile(self.user)
        get_user_profile(self.other_user)

        self.party = Party.objects.create(
            party_name="Difficulty Party",
            creator=self.user,
        )
        self.party.members.add(self.user, self.other_user)

    def test_create_task_form_allows_difficulty_ten(self):
        form = CreateTaskForm(
            data={
                "affiliation": self.party.id,
                "name": "Hard Quest",
                "description": "A very hard quest.",
                "difficulty_rating": 10,
                "recurring": 0,
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_task_form_rejects_difficulty_above_ten(self):
        form = CreateTaskForm(
            data={
                "affiliation": self.party.id,
                "name": "Too Hard Quest",
                "description": "This should fail.",
                "difficulty_rating": 11,
                "recurring": 0,
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("difficulty_rating", form.errors)

    def test_create_task_form_allows_recurring_zero(self):
        form = CreateTaskForm(
            data={
                "affiliation": self.party.id,
                "name": "One Time Quest",
                "description": "A normal one-time task.",
                "difficulty_rating": 4,
                "recurring": 0,
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_task_form_allows_positive_recurring_days(self):
        form = CreateTaskForm(
            data={
                "affiliation": self.party.id,
                "name": "Repeat Quest",
                "description": "A repeating task.",
                "difficulty_rating": 6,
                "recurring": 7,
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_task_form_rejects_negative_recurring_days(self):
        form = CreateTaskForm(
            data={
                "affiliation": self.party.id,
                "name": "Bad Repeat Quest",
                "description": "Negative recurring should fail.",
                "difficulty_rating": 6,
                "recurring": -1,
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("recurring", form.errors)

    def test_create_task_post_sets_points_to_difficulty_times_ten(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("QuestLog:create_task") + f"?guid={self.party.guid}",
            {
                "guid": str(self.party.guid),
                "affiliation": self.party.id,
                "name": "Ten Point Scale Quest",
                "description": "Testing point calculation.",
                "difficulty_rating": 7,
                "recurring": 0,
            },
        )

        self.assertEqual(response.status_code, 302)

        task = Task.objects.get(name="Ten Point Scale Quest")
        self.assertEqual(task.difficulty_rating, 7)
        self.assertEqual(task.point_value, 70)

    def test_create_task_post_saves_recurring_value(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("QuestLog:create_task") + f"?guid={self.party.guid}",
            {
                "guid": str(self.party.guid),
                "affiliation": self.party.id,
                "name": "Weekly Quest",
                "description": "Testing recurring save.",
                "difficulty_rating": 5,
                "recurring": 7,
            },
        )

        self.assertEqual(response.status_code, 302)

        task = Task.objects.get(name="Weekly Quest")
        self.assertEqual(task.recurring, 7)

    def test_task_sync_point_value_uses_difficulty_times_ten(self):
        task = Task.objects.create(
            owner=self.user,
            name="Sync Quest",
            description="Sync test",
            affiliation=self.party,
            difficulty_rating=8,
            recurring=0,
            point_value=0,
        )

        TaskDifficultyVote.objects.create(
            task=task,
            voter=self.user,
            rating=8,
        )

        task.sync_point_value_with_difficulty()
        task.refresh_from_db()

        self.assertEqual(task.point_value, 80)

    def test_vote_task_difficulty_accepts_ten(self):
        task = Task.objects.create(
            owner=self.user,
            name="Vote Quest",
            description="Voting test",
            affiliation=self.party,
            difficulty_rating=4,
            recurring=0,
            point_value=40,
        )

        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("QuestLog:vote_task_difficulty", args=[task.id]),
            {"rating": 10},
        )

        self.assertEqual(response.status_code, 302)

        vote = TaskDifficultyVote.objects.get(task=task, voter=self.other_user)
        self.assertEqual(vote.rating, 10)

    def test_tasks_page_shows_recurring_text_for_recurring_task(self):
        task = Task.objects.create(
            owner=self.user,
            name="Recurring Quest",
            description="Recurring task display test",
            affiliation=self.party,
            difficulty_rating=6,
            recurring=3,
            point_value=60,
            status=Task.Status.NOT_STARTED,
        )

        TaskDifficultyVote.objects.create(
            task=task,
            voter=self.user,
            rating=6,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("QuestLog:tasks"), {"guid": str(self.party.guid)})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Repeats every 3 days")

    def test_tasks_page_uses_ten_point_scale_text(self):
        task = Task.objects.create(
            owner=self.user,
            name="Scale Quest",
            description="Scale display test",
            affiliation=self.party,
            difficulty_rating=9,
            recurring=0,
            point_value=90,
            status=Task.Status.NOT_STARTED,
        )

        TaskDifficultyVote.objects.create(
            task=task,
            voter=self.user,
            rating=9,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("QuestLog:tasks"), {"guid": str(self.party.guid)})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/10")

    def test_about_page_shows_updated_feature_text(self):
        response = self.client.get(reverse("QuestLog:about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "About QuestLog")
        self.assertContains(response, "Difficulty & Points")
        self.assertContains(response, "Recurring Tasks")
        self.assertContains(response, "difficulty × 10")



    # def test_parties_view_uses_template_and_lists_parties(self):
    #     self.client.force_login(self.user)
    #     response = self.client.get(reverse("QuestLog:parties"))
    #     self.assertEqual(response.status_code, 200)
    #     self.assertTemplateUsed(response, "parties.html")
    #     self.assertIn("parties", response.context)
    #     self.assertIn(self.party, list(response.context["parties"]))

    # def test_party_details_view_uses_template_and_shows_party(self):
    #     self.client.force_login(self.user)
    #     response = self.client.get(
    #         reverse("QuestLog:party_details"),
    #         {"guid": str(self.party.guid)},
    #     )
    #     self.assertEqual(response.status_code, 200)
    #     self.assertTemplateUsed(response, "party_details.html")
    #     self.assertEqual(response.context.get("party"), self.party)

