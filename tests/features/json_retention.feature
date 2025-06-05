Feature: JSON Response Retention Policy
  As a system administrator
  I want to automatically clean up old JSON responses
  So that we comply with PII data retention policies

  Background:
    Given the database is initialized
    And the JSON retention policy is set to 90 days

  Scenario: JSON responses are stored with retention date
    When I save a business with Yelp JSON response
    And I save a business with Google JSON response
    Then the businesses should have json_retention_expires_at set
    And the retention date should be 90 days from now

  Scenario: Expired JSON responses are identified
    Given I have businesses with JSON responses:
      | name                | json_type | days_old |
      | Old Yelp Business   | yelp      | 91       |
      | Old Google Business | google    | 92       |
      | Recent Business     | both      | 30       |
    When I check for expired JSON responses
    Then I should find 2 businesses with expired JSON
    And "Recent Business" should not be in the expired list

  Scenario: Cleanup removes only JSON fields
    Given I have a business "Test Restaurant" with complete data and JSON responses
    And the JSON retention has expired
    When I run the JSON cleanup process
    Then the business "Test Restaurant" should have no JSON responses
    But the business should still have all other fields intact

  Scenario: Dry run mode shows what would be cleaned
    Given I have 5 businesses with expired JSON responses
    When I run the JSON cleanup in dry-run mode
    Then I should see that 5 businesses would be cleaned
    But no JSON data should actually be removed

  Scenario: Batch processing handles large volumes
    Given I have 100 businesses with expired JSON responses
    When I run the JSON cleanup with batch size 25
    Then all 100 businesses should have their JSON cleaned
    And the cleanup should have processed 4 batches

  Scenario: Statistics show JSON storage usage
    Given I have businesses with various JSON responses:
      | count | json_type | expired |
      | 50    | yelp      | no      |
      | 40    | google    | no      |
      | 30    | both      | no      |
      | 10    | yelp      | yes     |
      | 5     | google    | yes     |
    When I check JSON storage statistics
    Then I should see:
      | metric              | value |
      | yelp_json_count     | 90    |
      | google_json_count   | 75    |
      | expired_records     | 15    |

  Scenario: Nightly batch includes JSON cleanup
    Given I have businesses with expired JSON responses
    When the nightly batch job runs
    Then the JSON cleanup step should execute
    And expired JSON responses should be removed