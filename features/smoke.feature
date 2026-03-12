Feature: Smoke tests for core pages
  As a developer
  I want a baseline behavior test suite
  So I can quickly verify key pages render

  Scenario: Home page is reachable
    When I visit the path "/"
    Then the response status should be 200
    And the response should contain "Quest Log"

  Scenario: About page is reachable
    When I visit the path "/about/"
    Then the response status should be 200
    And the response should contain "Welcome to the Quest Log about page"

  Scenario: Tasks page is reachable
    When I visit the path "/tasks/"
    Then the response status should be 200

  Scenario: Complete task page is reachable
    When I visit the path "/complete_task/"
    Then the response status should be 200

  Scenario: Login page is reachable
    When I visit the path "/login/"
    Then the response status should be 200
    And the response should contain "Sign In"

  Scenario: Register page is reachable
    When I visit the path "/register/"
    Then the response status should be 200
    And the response should contain "Create Account"

  Scenario: Profile page redirects anonymous users
    When I visit the path "/profile/"
    Then the response status should be 302
    And the response should redirect to "/login/?next=/profile/"

  Scenario: Profile page is reachable for an authenticated user
    Given a Quest Log user exists with username "profilehero", display name "Profile Hero", and password "StrongPassword123!"
    And I am authenticated as "profilehero"
    When I visit the path "/profile/"
    Then the response status should be 200
    And the response should contain "Profile Hero"
