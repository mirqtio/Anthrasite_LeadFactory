Feature: Pipeline Stages
  As a marketing automation system
  I want to process leads through various pipeline stages
  So that I can generate qualified sales opportunities

  Background:
    Given the database is initialized
    And API mocks are configured

  Scenario: Scraping new business leads
    When I scrape businesses from source "test_source" with limit 10
    Then I should receive at least 2 businesses
    And each business should have a name and address
    And each business should be saved to the database

  Scenario: Enriching business data
    Given a business exists with basic information
    When I enrich the business data
    Then the business should have additional contact information
    And the business should have technology stack information
    And the business should have performance metrics
    And enrichment timestamp should be updated

  Scenario: Scoring business leads
    Given a business exists with enriched information
    When I score the business
    Then the business should have a score between 0 and 100
    And the score details should include component scores
    And businesses with better tech stacks should score higher
    And businesses with better performance should score higher

  Scenario: Generating emails for qualified leads
    Given a business exists with a high score
    When I generate an email for the business
    Then the email should have a subject line
    And the email should have HTML and text content
    And the email should be saved to the database with pending status

  Scenario: Processing the email queue
    Given there are emails in the queue with pending status
    When I process the email queue
    Then pending emails should be sent
    And the email status should be updated to sent
    And the sent timestamp should be recorded

  Scenario: Monitoring API costs
    Given API costs have been logged for various operations
    When I check the budget status
    Then I should see the total cost for the current month
    And I should see the cost breakdown by model
    And I should see the cost breakdown by purpose
    And I should know if we're within budget limits

  @e2e @real_api
  Scenario: Full lead processed and email delivered
    Given the database is initialized
    And a test lead is queued
    When the pipeline runs with real API keys
    Then a screenshot and mockup are generated
    And a real email is sent via SendGrid to EMAIL_OVERRIDE
    And the SendGrid response is 202
