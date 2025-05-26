Feature: Lead Deduplication
  As a marketing manager
  I want to identify and merge duplicate business records
  So that I can maintain a clean and accurate database of leads

  Background:
    Given the database is initialized
    And the API keys are configured

  Scenario: Identify exact duplicate businesses
    Given multiple businesses with identical names and addresses
    When I run the deduplication process
    Then the duplicate businesses should be identified
    And the duplicate businesses should be merged
    And the merged business should retain the highest score
    And the merged business should have all contact information

  Scenario: Identify similar businesses with fuzzy matching
    Given multiple businesses with similar names and addresses
    When I run the deduplication process with fuzzy matching
    Then the similar businesses should be identified
    And the similar businesses should be verified with LLM
    And the confirmed duplicates should be merged
    And the merged business should retain the highest score

  Scenario: Handle businesses with different addresses but same name
    Given multiple businesses with same name but different addresses
    When I run the deduplication process
    Then the businesses should be flagged for manual review
    And the businesses should not be automatically merged
    And the process should continue to the next set of businesses

  Scenario: Handle API errors gracefully
    Given multiple businesses with similar names and addresses
    And the LLM verification API is unavailable
    When I run the deduplication process with fuzzy matching
    Then the error should be logged
    And the businesses should be flagged for manual review
    And the process should continue without crashing

  Scenario: Skip already processed businesses
    Given multiple businesses that have already been processed for deduplication
    When I run the deduplication process
    Then the businesses should be skipped
    And the deduplication process should continue to the next set
