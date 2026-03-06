"""
This file is for all test cases for Django
When you add a new view there should be a test case function added to ViewReachabilityTests class
"""

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
