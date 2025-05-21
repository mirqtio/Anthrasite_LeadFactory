Feature: Batch Completion Tracking and Alerting
  As a system operator
  I want to track batch completion status and receive alerts for incomplete batches
  So that I can quickly identify and resolve issues with the nightly batch process

  Background:
    Given the batch tracker system is initialized

  Scenario: Record batch start
    When I record a batch start
    Then the batch start timestamp should be saved
    And the batch completion gauge should be reset to 0% for all stages

  Scenario: Record batch stage completion
    Given a batch has been started
    When I record completion of the "scrape" stage at 16.67%
    Then the "scrape" stage completion should be recorded as 16.67%
    And the batch completion gauge should show 16.67% for the "scrape" stage

  Scenario: Record batch end
    Given a batch has been started
    And all stages have been completed
    When I record a batch end
    Then the batch end timestamp should be saved
    And the batch completion gauge should show 100% for all stages

  Scenario: Check batch completion before deadline
    Given a batch has been started
    And the batch has been completed today
    When I check batch completion status
    Then the system should report the batch as completed on time
    And no alert should be triggered

  Scenario: Check batch completion after deadline with no completion
    Given a batch has been started
    And the batch has not been completed
    And the time is after the completion deadline
    When I check batch completion status
    Then the system should report the batch as not completed on time
    And an alert should be triggered

  Scenario: Check batch completion after deadline with completion
    Given a batch has been started
    And the batch has been completed today
    And the time is after the completion deadline
    When I check batch completion status
    Then the system should report the batch as completed on time
    And no alert should be triggered

  Scenario: Send alert email for incomplete batch
    Given a batch has not been completed on time
    When the batch completion monitor runs
    Then an alert email should be sent
    And the alert should contain batch status information
