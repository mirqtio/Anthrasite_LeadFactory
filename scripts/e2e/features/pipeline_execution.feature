Feature: E2E Pipeline Execution and Resolution
  As a quality engineer
  I want to ensure the entire lead processing pipeline works correctly
  So that I can be confident in the production readiness of the system

  Background:
    Given the preflight checks have been completed successfully
    And the test environment is configured with valid API keys
    And the test database is running with proper schema

  Scenario: Full lead processed and email delivered
    Given a test lead is queued
    When the pipeline runs with real API keys
    Then a screenshot and mockup are generated
    And a real email is sent via SendGrid to EMAIL_OVERRIDE
    And the SendGrid response is 202

  Scenario: System detects and logs environment variable issues
    Given the environment is missing a required variable "SENDGRID_API_KEY"
    When the pipeline preflight check runs
    Then the execution status should be "failure"
    And the failure category should be "environment_issue"
    And the resolution should suggest adding the missing variable

  Scenario: System retries and recovers from transient API failures
    Given the OpenAI API is temporarily unavailable
    When the pipeline runs with retry enabled
    Then the API test should be retried
    And the execution should eventually succeed
    And the retry count should be greater than 0

  Scenario: System generates comprehensive execution report
    Given a pipeline execution has completed
    When the report generator runs
    Then an execution summary is generated
    And the report includes execution statistics
    And the report includes test coverage analysis
    And the report includes failure analysis if applicable

  Scenario: System identifies recurring failure patterns
    Given multiple pipeline executions have been recorded
    When the trend report generator runs
    Then common failure patterns are identified
    And recommendations are provided for improving reliability
    And success rate statistics are included in the report
