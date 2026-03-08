"""
This file is for all test cases for Django
When you add a new view there should be a test case function added to ViewReachabilityTests class
For testing the deployment there is a DeploymentEnrtypointTests class that will ensure the deployments work
I also added a class SettingsBranchCoverageTests for ensuring the seetings for the project are working as expected
"""

import importlib
import os
import sys

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
