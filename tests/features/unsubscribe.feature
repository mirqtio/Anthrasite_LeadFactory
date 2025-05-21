Feature: Email Unsubscribe Functionality
  As a lead in the database
  I want to be able to unsubscribe from marketing emails
  So that I can opt out of receiving unwanted communications

  Background:
    Given a user with email 'test@example.com'

  Scenario: Check if a user is not unsubscribed
    Given the user has not unsubscribed
    When I check if the email 'test@example.com' is unsubscribed
    Then the result should be 'False'

  Scenario: Check if a user is unsubscribed
    Given the user has unsubscribed
    When I check if the email 'test@example.com' is unsubscribed
    Then the result should be 'True'

  Scenario: Add a user to the unsubscribe list
    Given the user has not unsubscribed
    When I add the email 'test@example.com' to the unsubscribe list
    Then the email 'test@example.com' should be in the unsubscribe list

  Scenario: Do not send email to unsubscribed user
    Given the user has unsubscribed
    When I try to send an email to 'test@example.com'
    Then the email should not be sent

  Scenario: Send email to subscribed user
    Given the user has not unsubscribed
    When I try to send an email to 'test@example.com'
    Then the email should be sent

  Scenario: User visits unsubscribe page
    When a user visits the unsubscribe page with email 'test@example.com'
    Then the response status code should be 200
    And the response should contain 'Unsubscribe from Anthrasite Web Services'

  Scenario: User submits unsubscribe form
    When a user submits the unsubscribe form with email 'test@example.com'
    Then the response status code should be 200
    And the response should contain 'successfully unsubscribed'
    And the email 'test@example.com' should be in the unsubscribe list

  Scenario: Verify CAN-SPAM compliance in HTML email template
    Then the HTML email template should contain the physical address
    And the HTML email template should contain an unsubscribe link

  Scenario: Verify CAN-SPAM compliance in plain text email
    Then the plain text email should contain the physical address
    And the plain text email should contain unsubscribe instructions
