Feature: Fallback & Retry Error Management
  As a pipeline operator
  I want to automatically fix common errors and manage error resolution in bulk
  So that pipeline reliability is improved and manual intervention is minimized

  Background:
    Given the pipeline error handling system is initialized
    And manual fix scripts are available
    And error aggregation is enabled

  Scenario: Manual fix script automatically resolves database connection error
    Given a database connection timeout error occurs
    When the manual fix orchestrator processes the error
    Then the database connection fix script should be applied
    And the database connection should be restored
    And the error should be marked as resolved
    And the fix execution should be logged

  Scenario: Manual fix script handles network timeout with exponential backoff
    Given a network timeout error occurs in the scraping stage
    When the network timeout fix script is applied
    Then the timeout configuration should be increased
    And the operation should be marked for retry with exponential backoff
    And the fix execution should be successful

  Scenario: Validation error fix script cleans invalid data
    Given a business has invalid phone number format
    And a validation error is reported for the phone number
    When the validation error fix script processes the error
    Then the phone number should be cleaned and formatted
    And the business data should be updated in storage
    And the validation error should be resolved

  Scenario: Resource exhaustion fix script frees up space
    Given a "disk space full" error occurs
    When the resource exhaustion fix script is applied
    Then temporary files should be cleaned up
    And old log files should be removed
    And the available disk space should increase
    And the error should be marked as fixed

  Scenario: External API error fix script rotates API keys
    Given an "API key invalid" error occurs for OpenAI service
    When the external API fix script processes the error
    Then the API key should be rotated to a backup key
    And the service should be marked for retry
    And the fix should be recorded as successful

  Scenario: Fix script cannot resolve error and requires manual intervention
    Given a complex configuration error occurs
    When no fix scripts can handle the error
    Then the error should be marked as requiring manual intervention
    And an alert should be generated for the operations team
    And the error should remain in pending status

  Scenario: Bulk dismiss multiple errors with specified reason
    Given multiple errors exist in the system:
      | error_id | severity | category   | stage  |
      | err_001  | low      | network    | scrape |
      | err_002  | medium   | validation | enrich |
      | err_003  | low      | timeout    | score  |
    When I bulk dismiss errors "err_001,err_002,err_003" with reason "false_positive"
    And I provide comment "These are not actual errors"
    Then all selected errors should be marked as dismissed
    And the dismissal reason should be recorded
    And the dismissal comment should be stored
    And the user performing the dismissal should be logged

  Scenario: Bulk categorize errors with new severity and category
    Given multiple uncategorized errors exist:
      | error_id | current_severity | current_category |
      | err_010  | medium          | business_logic   |
      | err_011  | medium          | business_logic   |
      | err_012  | medium          | business_logic   |
    When I bulk categorize errors "err_010,err_011,err_012"
    And I set the category to "validation"
    And I set the severity to "high"
    And I add tags "urgent,investigate"
    Then all selected errors should have category "validation"
    And all selected errors should have severity "high"
    And all selected errors should have tags "urgent,investigate"
    And the update should be logged with user information

  Scenario: Bulk fix attempts on multiple errors
    Given multiple fixable errors exist:
      | error_id | error_type          | category     | fixable |
      | err_020  | ConnectionTimeout   | network      | yes     |
      | err_021  | ValidationError     | validation   | yes     |
      | err_022  | ConfigurationError  | config       | no      |
    When I initiate bulk fix for errors "err_020,err_021,err_022"
    And I set max fixes per error to 3
    Then fix scripts should be applied to err_020 and err_021
    And err_020 should be successfully fixed
    And err_021 should be successfully fixed
    And err_022 should be marked as "no applicable fixes"
    And a fix execution report should be generated

  Scenario: Error dashboard shows real-time metrics
    Given errors have occurred in the last 24 hours:
      | error_id | severity | timestamp           | fixed |
      | err_030  | critical | 2024-01-01T10:00:00 | no    |
      | err_031  | high     | 2024-01-01T11:00:00 | yes   |
      | err_032  | medium   | 2024-01-01T12:00:00 | no    |
    When I request the error dashboard data
    Then the dashboard should show total errors as 3
    And the dashboard should show critical errors as 1
    And the dashboard should show fixed errors as 1
    And error trends should be calculated correctly
    And top error patterns should be identified

  Scenario: Fix script monitoring detects performance issues
    Given a fix script has execution history:
      | execution_id | result      | duration_seconds | timestamp           |
      | fix_001      | success     | 5.2             | 2024-01-01T10:00:00 |
      | fix_002      | success     | 45.8            | 2024-01-01T11:00:00 |
      | fix_003      | failed      | 62.1            | 2024-01-01T12:00:00 |
      | fix_004      | success     | 58.9            | 2024-01-01T13:00:00 |
    When the fix script monitor analyzes performance
    Then a performance degradation alert should be generated
    And the average duration should exceed the warning threshold
    And recommendations should include "Investigate performance bottlenecks"

  Scenario: Fix script monitoring detects low success rate
    Given a fix script has recent executions with low success rate:
      | execution_id | result  | timestamp           |
      | fix_010      | failed  | 2024-01-01T10:00:00 |
      | fix_011      | failed  | 2024-01-01T11:00:00 |
      | fix_012      | success | 2024-01-01T12:00:00 |
      | fix_013      | failed  | 2024-01-01T13:00:00 |
      | fix_014      | failed  | 2024-01-01T14:00:00 |
    When the fix script monitor calculates success rate
    Then the success rate should be 20%
    And a low success rate alert should be triggered
    And recommendations should include script review actions

  Scenario: Error pattern detection identifies recurring issues
    Given multiple similar errors have occurred:
      | error_id | error_type        | stage  | operation | business_id |
      | err_040  | ConnectionTimeout | scrape | fetch_url | 123         |
      | err_041  | ConnectionTimeout | scrape | fetch_url | 124         |
      | err_042  | ConnectionTimeout | scrape | fetch_url | 125         |
      | err_043  | ConnectionTimeout | scrape | fetch_url | 126         |
    When the error aggregator analyzes patterns
    Then a pattern should be identified for "ConnectionTimeout in scrape.fetch_url"
    And the pattern frequency should be 4
    And the pattern should include affected business IDs
    And recommendations should be generated for the pattern

  Scenario: Circuit breaker prevents cascading failures during fix attempts
    Given a fix script has a high failure rate
    And the circuit breaker is configured with failure threshold 3
    When the fix script fails 3 consecutive times
    Then the circuit breaker should open
    And subsequent fix attempts should be rejected
    And the circuit breaker status should be logged
    And manual intervention should be flagged

  Scenario: Circuit breaker recovery after successful fixes
    Given the circuit breaker is in open state
    And the recovery timeout has elapsed
    When a fix attempt is made
    Then the circuit breaker should transition to half-open
    And if the fix succeeds
    Then the circuit breaker should close
    And normal operation should resume

  Scenario: Error fix orchestrator coordinates multiple fix scripts
    Given a complex error that could be handled by multiple fix scripts
    When the fix orchestrator processes the error
    Then applicable fix scripts should be identified
    And fix scripts should be executed in priority order
    And execution should stop after first successful fix
    And all attempts should be logged

  Scenario: Error management API handles bulk operations with validation
    Given the error management API is available
    When I send a bulk dismiss request with invalid error IDs
    Then the API should return appropriate error messages
    And the response should indicate which errors were not found
    And valid errors should still be processed
    And the operation should be partially successful

  Scenario: Error management UI provides real-time feedback
    Given the error management UI is loaded
    And multiple errors are displayed
    When I select errors for bulk dismissal
    Then the bulk actions panel should become visible
    And the selected count should be updated
    And when I submit the bulk dismissal
    Then a loading indicator should be shown
    And success/failure feedback should be displayed
    And the error list should be refreshed

  Scenario: Error trend analysis shows improvement over time
    Given historical error data spans multiple days
    And fix scripts have been applied over time
    When I analyze error trends for the past week
    Then the trend analysis should show decreasing error rates
    And fix script effectiveness should be measured
    And improvement recommendations should be provided

  Scenario: Alert system notifies of critical error management issues
    Given the error monitoring system is active
    When critical errors exceed the threshold
    Or fix script success rates drop below acceptable levels
    Then appropriate alerts should be generated
    And alert severity should be calculated correctly
    And recommended actions should be provided
    And alerts should be deduplicated to avoid spam
