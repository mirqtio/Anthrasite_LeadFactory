Feature: Modern Site Filtering
  As a lead generation system
  I want to skip modern, well-optimized websites
  So that we don't waste resources on sites that don't need improvement

  Background:
    Given the PageSpeed Insights API is available
    And the enrichment pipeline is configured

  Scenario: Skip a modern website with high performance and mobile responsiveness
    Given a business with website "https://modern-tech.com"
    And the website has a PageSpeed performance score of 95
    And the website is mobile responsive
    When the business is enriched
    Then the business should be marked as "modern_site_skipped"
    And no email should be sent to this business
    And the skip reason should be "modern_site"

  Scenario: Process an outdated website with poor performance
    Given a business with website "https://old-store.com"
    And the website has a PageSpeed performance score of 45
    And the website is not mobile responsive
    When the business is enriched
    Then the business should be processed normally
    And the business should be eligible for email outreach
    And no skip reason should be set

  Scenario: Process a website with good performance but not mobile responsive
    Given a business with website "https://desktop-only.com"
    And the website has a PageSpeed performance score of 92
    And the website is not mobile responsive
    When the business is enriched
    Then the business should be processed normally
    And the business should be eligible for email outreach
    And no skip reason should be set

  Scenario: Continue processing when PageSpeed API fails
    Given a business with website "https://example.com"
    And the PageSpeed API returns an error
    When the business is enriched
    Then the business should be processed normally
    And the business should be eligible for email outreach
    And a warning should be logged about PageSpeed failure

  Scenario: Boundary case - exactly 90% performance score
    Given a business with website "https://boundary-case.com"
    And the website has a PageSpeed performance score of 90
    And the website is mobile responsive
    When the business is enriched
    Then the business should be marked as "modern_site_skipped"
    And no email should be sent to this business

  Scenario: Multiple modern sites in batch processing
    Given the following businesses:
      | name          | website                  | performance | mobile_responsive |
      | Modern Co     | https://modern-co.com    | 95         | true              |
      | Old Shop      | https://old-shop.com     | 40         | false             |
      | Fast Site     | https://fast-site.com    | 93         | true              |
      | Desktop Site  | https://desktop.com      | 91         | false             |
    When the businesses are enriched in batch
    Then the following businesses should be skipped:
      | name      | reason       |
      | Modern Co | modern_site  |
      | Fast Site | modern_site  |
    And the following businesses should be processed:
      | name         |
      | Old Shop     |
      | Desktop Site |
