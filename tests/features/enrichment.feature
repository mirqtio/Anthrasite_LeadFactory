
Feature: Lead Enrichment
  As a marketing manager
  I want to enrich business data with additional information
  So that I can better understand and target potential leads

  Background:
    Given the database is initialized
    And the API keys are configured

  Scenario: Enrich business with website data
    Given a business with a website
    When I run the enrichment process
    Then the business should have technical stack information
    And the business should have performance metrics
    And the business should have contact information
    And the enriched data should be saved to the database

  Scenario: Enrich business without website
    Given a business without a website
    When I run the enrichment process
    Then the business should be marked for manual review
    And the business should have a status of "needs_website"
    And the enrichment process should continue to the next business

  Scenario: Handle API errors gracefully
    Given a business with a website
    And the enrichment API is unavailable
    When I run the enrichment process
    Then the error should be logged
    And the business should be marked for retry
    And the process should continue without crashing

  Scenario: Skip already enriched businesses
    Given a business that has already been enriched
    When I run the enrichment process
    Then the business should be skipped
    And the enrichment process should continue to the next business

  Scenario: Prioritize businesses by score
    Given multiple businesses with different scores
    When I run the enrichment process with prioritization
    Then businesses should be processed in descending score order
