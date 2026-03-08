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
