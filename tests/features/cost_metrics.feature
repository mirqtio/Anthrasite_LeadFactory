Feature: Cost Metrics Tracking and Alerting
  As a system operator
  I want to track cost metrics and receive alerts for high costs
  So that I can monitor and control expenses

  Background:
    Given the cost metrics system is initialized

  Scenario: Calculate cost per lead
    Given there are 100 leads in the database
    And the total monthly cost is $300
    When I calculate the cost per lead
    Then the cost per lead should be $3.00
    And the cost per lead metric should be updated

  Scenario: Cost per lead threshold check - below threshold
    Given the cost per lead is $2.50
    When I check the cost per lead threshold of $3.00
    Then the system should report the cost per lead is within threshold
    And no alert should be triggered

  Scenario: Cost per lead threshold check - above threshold
    Given the cost per lead is $3.50
    When I check the cost per lead threshold of $3.00
    Then the system should report the cost per lead exceeds threshold
    And an alert should be triggered

  Scenario: Track GPU usage with GPU_BURST flag enabled
    Given the GPU_BURST flag is enabled
    When I track GPU usage with cost $0.50
    Then the GPU cost should be incremented by $0.50
    And the GPU cost metric should be updated

  Scenario: Track GPU usage with GPU_BURST flag disabled
    Given the GPU_BURST flag is disabled
    When I track GPU usage with cost $0.50
    Then the GPU cost should not be incremented
    And the GPU cost metric should not be updated

  Scenario: GPU cost threshold check - below threshold
    Given the daily GPU cost is $20.00
    And the monthly GPU cost is $80.00
    When I check the GPU cost thresholds of $25.00 daily and $100.00 monthly
    Then the system should report the GPU cost is within thresholds
    And no alert should be triggered

  Scenario: GPU cost threshold check - above daily threshold
    Given the daily GPU cost is $30.00
    And the monthly GPU cost is $80.00
    When I check the GPU cost thresholds of $25.00 daily and $100.00 monthly
    Then the system should report the GPU cost exceeds daily threshold
    And an alert should be triggered

  Scenario: GPU cost threshold check - above monthly threshold
    Given the daily GPU cost is $20.00
    And the monthly GPU cost is $120.00
    When I check the GPU cost thresholds of $25.00 daily and $100.00 monthly
    Then the system should report the GPU cost exceeds monthly threshold
    And an alert should be triggered

  Scenario: Update cost metrics at batch end
    Given there are 100 leads in the database
    And the total monthly cost is $300
    And the daily GPU cost is $20.00
    And the monthly GPU cost is $80.00
    When I update cost metrics at batch end
    Then the cost per lead should be $3.00
    And the cost per lead metric should be updated
    And the system should report all cost metrics
