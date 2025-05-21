
Feature: Lead Scraper
  As a marketing manager
  I want to scrape business listings from Yelp and Google
  So that I can build a database of potential leads

  Background:
    Given the database is initialized
    And the API keys are configured

  Scenario: Scrape businesses from Yelp API
    Given a target ZIP code "10002"
    And a target vertical "restaurants"
    When I run the scraper for Yelp API
    Then at least 5 businesses should be found
    And the businesses should have the required fields
    And the businesses should be saved to the database

  Scenario: Scrape businesses from Google Places API
    Given a target ZIP code "98908"
    And a target vertical "retail"
    When I run the scraper for Google Places API
    Then at least 5 businesses should be found
    And the businesses should have the required fields
    And the businesses should be saved to the database

  Scenario: Handle API errors gracefully
    Given a target ZIP code "10002"
    And a target vertical "restaurants"
    And the API is unavailable
    When I run the scraper
    Then the error should be logged
    And the process should continue without crashing

  Scenario: Skip existing businesses
    Given a target ZIP code "10002"
    And a target vertical "restaurants"
    And some businesses already exist in the database
    When I run the scraper
    Then only new businesses should be added
    And duplicate businesses should be skipped
