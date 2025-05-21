
Feature: Email Queue
  As a marketing manager
  I want to send personalized emails to potential leads
  So that I can initiate contact and demonstrate value

  Background:
    Given the database is initialized
    And the API keys are configured

  Scenario: Send personalized email with mockup
    Given a high-scoring business with mockup data
    When I run the email queue process
    Then a personalized email should be sent
    And the email should include the mockup data
    And the email should have a personalized subject line
    And the email record should be saved to the database
    And the cost should be tracked

  Scenario: Skip businesses without mockup data
    Given a business without mockup data
    When I run the email queue process
    Then the business should be skipped
    And the email queue process should continue to the next business

  Scenario: Handle API errors gracefully
    Given a business with mockup data
    And the email sending API is unavailable
    When I run the email queue process
    Then the error should be logged
    And the business should be marked for retry
    And the process should continue without crashing

  Scenario: Respect daily email limit
    Given multiple businesses with mockup data
    And the daily email limit is set to 2
    When I run the email queue process
    Then only 2 emails should be sent
    And the process should stop after reaching the limit
    And the remaining businesses should be left for the next run

  Scenario: Track bounce rates
    Given a business with a high bounce rate domain
    When I run the email queue process
    Then the business should be flagged for manual review
    And no email should be sent to the high bounce rate domain
    And the process should continue to the next business

  Scenario: Use dry run mode
    Given a business with mockup data
    When I run the email queue process in dry run mode
    Then the email should be prepared but not sent
    And the process should log the email content
    And no cost should be tracked
