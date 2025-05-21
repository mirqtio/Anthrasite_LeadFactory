
Feature: Mockup Generation
  As a marketing manager
  I want to generate website improvement mockups for potential leads
  So that I can demonstrate value in initial outreach

  Background:
    Given the database is initialized
    And the API keys are configured

  Scenario: Generate mockup for high-scoring business
    Given a high-scoring business with website data
    When I run the mockup generation process
    Then a premium mockup should be generated
    And the mockup should include multiple improvement suggestions
    And the mockup should be saved to the database
    And the cost should be tracked

  Scenario: Generate mockup for medium-scoring business
    Given a medium-scoring business with website data
    When I run the mockup generation process
    Then a standard mockup should be generated
    And the mockup should include basic improvement suggestions
    And the mockup should be saved to the database
    And the cost should be tracked

  Scenario: Generate mockup for low-scoring business
    Given a low-scoring business with website data
    When I run the mockup generation process
    Then a basic mockup should be generated
    And the mockup should include minimal improvement suggestions
    And the mockup should be saved to the database
    And the cost should be tracked

  Scenario: Handle API errors gracefully
    Given a business with website data
    And the mockup generation API is unavailable
    When I run the mockup generation process
    Then the error should be logged
    And the business should be marked for retry
    And the process should continue without crashing

  Scenario: Skip businesses without website data
    Given a business without website data
    When I run the mockup generation process
    Then the business should be skipped
    And the mockup generation process should continue to the next business

  Scenario: Use fallback model when primary model fails
    Given a business with website data
    And the primary model is unavailable
    When I run the mockup generation process
    Then the fallback model should be used
    And a mockup should still be generated
    And the mockup should be saved to the database
    And the cost should be tracked for the fallback model
