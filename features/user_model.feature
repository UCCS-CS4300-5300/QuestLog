Feature: Quest Log account profile behavior
  As a developer
  I want behavior tests for account profiles and authentication
  So CI can catch regressions in account storage and login flows

  Scenario: Creating a user stores the core account fields
    When I create a Quest Log user with username "quester", display name "myliluserlmao", and password "mylilpasslmao"
    Then a Quest Log user with username "quester" should exist
    And the user "quester" should have display name "myliluserlmao"
    And the user "quester" should have a usable password "mylilpasslmao"

  Scenario: Users can store a profile picture
    When I create a Quest Log user with username "mylilusername", display name "mylildisplayname", password "mylilpasslmao", and a profile picture
    Then a Quest Log user with username "mylilusername" should exist
    And the user "mylilusername" should have a stored profile picture

  Scenario: The sign up page creates a Quest Log user
    When I submit the sign up form for username "signuphero", display name "Sign Up Hero", and password "mylilpasslmao"
    Then the response status should be 302
    And the response should redirect to "/profile/"
    And a Quest Log user with username "signuphero" should exist
    And the authenticated user should be "signuphero"

  Scenario: The login page authenticates a Quest Log user
    Given a Quest Log user exists with username "lilloginbroagain", display name "lilloginbro", and password "mylilpasslmao"
    When I submit the login form for username "lilloginbroagain" and password "mylilpasslmao"
    Then the response status should be 302
    And the response should redirect to "/profile/"
    And the authenticated user should be "lilloginbroagain"
