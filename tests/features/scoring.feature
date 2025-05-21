
Feature: Lead Scoring
  As a marketing manager
  I want to score leads based on defined rules
  So that I can prioritize outreach to the most promising leads

  Background:
    Given the database is initialized
    And the scoring rules are configured

  Scenario: Score leads based on tech stack
    Given a business with WordPress in its tech stack
    When I run the scoring process
    Then the business should receive points for WordPress
    And the score details should include tech stack information
    And the final score should be saved to the database

  Scenario: Score leads based on performance metrics
    Given a business with poor performance metrics
    When I run the scoring process
    Then the business should receive points for poor performance
    And the score details should include performance information
    And the final score should be saved to the database

  Scenario: Score leads based on location
    Given a business in a target location
    When I run the scoring process
    Then the business should receive points for location
    And the score details should include location information
    And the final score should be saved to the database

  Scenario: Handle missing data gracefully
    Given a business with incomplete data
    When I run the scoring process
    Then the business should be scored based on available data
    And missing data points should be noted in the score details
    And the process should continue without crashing

  Scenario: Apply rule weights correctly
    Given a business matching multiple scoring rules
    When I run the scoring process
    Then the business should receive weighted points for each matching rule
    And the final score should be the sum of all weighted points
    And the score details should include all applied rules
