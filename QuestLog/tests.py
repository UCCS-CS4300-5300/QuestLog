from django.test import TestCase, Client
from django.urls import reverse, resolve
from . import views


class HomeViewTests(TestCase):
    """Tests for the home page view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('QuestLog:home')

    def test_home_url_resolves_to_home_view(self):
        self.assertEqual(resolve(self.url).func, views.home)

    def test_home_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_home_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_extends_base_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'base.html')

    def test_home_contains_welcome_heading(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Welcome to the Quest Log')

    def test_home_contains_link_to_about(self):
        response = self.client.get(self.url)
        about_url = reverse('QuestLog:about')
        self.assertContains(response, about_url)


class AboutViewTests(TestCase):
    """Tests for the about page view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('QuestLog:about')

    def test_about_url_resolves_to_about_view(self):
        self.assertEqual(resolve(self.url).func, views.about)

    def test_about_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_about_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'about.html')

    def test_about_extends_base_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'base.html')

    def test_about_contains_welcome_heading(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Welcome to the Quest Log about page')

    def test_about_contains_stakeholders_section(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Stakeholders')
        self.assertContains(response, 'Primary stakeholders')
        self.assertContains(response, 'Secondary stakeholders')

    def test_about_contains_link_to_home(self):
        response = self.client.get(self.url)
        home_url = reverse('QuestLog:home')
        self.assertContains(response, home_url)


class URLTests(TestCase):
    """Tests for URL configuration."""

    def test_home_reverse_matches_root(self):
        self.assertEqual(reverse('QuestLog:home'), '/')

    def test_about_reverse_matches_about_path(self):
        self.assertEqual(reverse('QuestLog:about'), '/about/')
