Feature: Local Screenshot Capture
  As a system operator
  I want to capture website screenshots locally
  So that I can reduce costs and have a fallback when external APIs fail

  Background:
    Given the screenshot capture system is initialized

  Scenario: Capture screenshot with ScreenshotOne API
    Given I have a ScreenshotOne API key configured
    When I capture a screenshot of "https://example.com"
    Then the screenshot should be captured using ScreenshotOne API
    And the screenshot file should be created
    And an asset record should be created in the database

  Scenario: Fallback to local capture when no API key
    Given I have no ScreenshotOne API key configured
    And Playwright is installed and available
    When I capture a screenshot of "https://example.com"
    Then the screenshot should be captured using Playwright
    And the screenshot file should be created
    And an asset record should be created in the database

  Scenario: API failure triggers local fallback
    Given I have a ScreenshotOne API key configured
    And Playwright is installed and available
    But the ScreenshotOne API returns an error
    When I capture a screenshot of "https://example.com"
    Then the system should fallback to Playwright capture
    And the screenshot file should be created

  Scenario: Placeholder generation in test mode
    Given I am running in test mode
    And Playwright is not available
    When I capture a screenshot of "https://example.com"
    Then a placeholder screenshot should be generated
    And the placeholder should contain the business name and URL

  Scenario: All methods fail outside test mode
    Given I have no ScreenshotOne API key configured
    And Playwright is not available
    And I am not in test mode
    When I try to capture a screenshot of "https://example.com"
    Then the screenshot generation should fail with an error

  Scenario: Batch screenshot processing
    Given I have multiple businesses needing screenshots:
      | id  | name           | website                |
      | 101 | Test Shop 1    | https://shop1.example  |
      | 102 | Test Shop 2    | https://shop2.example  |
      | 103 | Test Shop 3    | https://shop3.example  |
    And Playwright is available
    When I process screenshots for all businesses
    Then 3 screenshots should be generated
    And 3 asset records should be created

  Scenario: Invalid URL handling
    Given Playwright is available
    When I capture a screenshot of "not-a-valid-url"
    Then Playwright should add https:// protocol automatically
    And attempt to capture the screenshot

  Scenario: Screenshot with custom viewport
    Given Playwright is available
    When I capture a screenshot with viewport 1920x1080
    Then the screenshot should have the specified dimensions

  Scenario: Cost tracking for API usage
    Given I have a ScreenshotOne API key configured
    And cost tracking is enabled
    When I capture a screenshot using the API
    Then the cost should be logged as 1 cent per screenshot

  Scenario: Local capture has zero cost
    Given Playwright is available
    When I capture a screenshot using local capture
    Then no cost should be recorded for the screenshot
