Feature: Skip Modern Sites in Lead Funnel
  As a lead generation system
  I want to skip modern, high-performing websites
  So that I don't waste resources on sites that don't need redesign

  Background:
    Given the lead factory system is running
    And the PageSpeed API is available
    And the enrichment pipeline is configured

  Scenario: Skip a modern site with high performance scores
    Given a business "TechCorp" with website "https://modern-tech.com"
    And the website has a PageSpeed performance score of 95
    And the website has a PageSpeed accessibility score of 88
    When the enrichment process runs for "TechCorp"
    Then the business should be marked with status "skipped_modern_site"
    And no screenshot should be captured
    And no email should be queued for the business
    And the features table should contain a skip reason of "modern_site"

  Scenario: Process an outdated site with low performance scores
    Given a business "OldShop" with website "https://legacy-store.com"
    And the website has a PageSpeed performance score of 42
    And the website has a PageSpeed accessibility score of 55
    When the enrichment process runs for "OldShop"
    Then the business should remain with status "pending"
    And a screenshot should be captured if configured
    And the business should be eligible for email outreach
    And the features table should contain the actual performance score of 42

  Scenario: Handle edge case at exact threshold
    Given a business "EdgeCase Inc" with website "https://edge-case.com"
    And the website has a PageSpeed performance score of 90
    And the website has a PageSpeed accessibility score of 80
    When the enrichment process runs for "EdgeCase Inc"
    Then the business should be marked with status "skipped_modern_site"
    And the skip should be logged with reason "modern_site"

  Scenario: Process site just below performance threshold
    Given a business "AlmostModern" with website "https://almost-there.com"
    And the website has a PageSpeed performance score of 89
    And the website has a PageSpeed accessibility score of 85
    When the enrichment process runs for "AlmostModern"
    Then the business should remain with status "pending"
    And the site should be processed normally

  Scenario: Process site just below accessibility threshold
    Given a business "NeedsAccess" with website "https://needs-access.com"
    And the website has a PageSpeed performance score of 95
    And the website has a PageSpeed accessibility score of 79
    When the enrichment process runs for "NeedsAccess"
    Then the business should remain with status "pending"
    And the site should be processed normally

  Scenario: Skipped sites are not reprocessed
    Given a business "AlreadySkipped" with status "skipped_modern_site"
    And the business has a features record with skip_reason "modern_site"
    When getting businesses to enrich
    Then "AlreadySkipped" should not be in the enrichment queue

  Scenario: Modern site skip reduces API costs
    Given 10 businesses with various websites
    And 5 of them have modern, high-performing sites
    And 5 of them have outdated, low-performing sites
    When the enrichment process runs for all businesses
    Then only 5 businesses should have screenshots captured
    And only 5 businesses should be queued for personalization
    And the cost tracking should show reduced API usage