Feature: Quest Log user model behavior
  As a developer
  I want behavior tests for the custom user model
  So CI can catch regressions in account storage and authentication

  Scenario: Creating a user stores the core account fields
    When I create a Quest Log user with username "quester", display name "Quest Master", and password "StrongPassword123!"
    Then a Quest Log user with username "quester" should exist
    And the user "quester" should have display name "Quest Master"
    And the user "quester" should have a usable password "StrongPassword123!"

  Scenario: Users can store a profile picture
    When I create a Quest Log user with username "avatarhero", display name "Avatar Hero", password "StrongPassword123!", and a profile picture
    Then a Quest Log user with username "avatarhero" should exist
    And the user "avatarhero" should have a stored profile picture

  Scenario: The sign up page creates a Quest Log user
    When I submit the sign up form for username "signuphero", display name "Sign Up Hero", and password "StrongPassword123!"
    Then the response status should be 302
    And the response should redirect to "/profile/"
    And a Quest Log user with username "signuphero" should exist
    And the authenticated user should be "signuphero"

  Scenario: The login page authenticates a Quest Log user
    Given a Quest Log user exists with username "loginhero", display name "Login Hero", and password "StrongPassword123!"
    When I submit the login form for username "loginhero" and password "StrongPassword123!"
    Then the response status should be 302
    And the response should redirect to "/profile/"
    And the authenticated user should be "loginhero"
