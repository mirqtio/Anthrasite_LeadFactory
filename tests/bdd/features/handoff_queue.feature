Feature: Handoff Queue Management
  As a sales manager
  I want to manage qualified leads in a handoff queue
  So that my sales team can efficiently follow up on prospects

  Background:
    Given the handoff queue system is initialized
    And qualification criteria exist in the system
    And sales team members are configured

  Scenario: Bulk qualify businesses for handoff
    Given I have a list of businesses with various scores
    And I select qualification criteria with minimum score of 70
    When I perform bulk qualification on the businesses
    Then only businesses meeting the criteria should be qualified
    And qualified businesses should be added to the handoff queue
    And an operation record should track the qualification process

  Scenario: Filter handoff queue by status
    Given there are queue entries with different statuses
    When I filter the queue by "qualified" status
    Then I should only see qualified entries
    And the entries should be sorted by priority

  Scenario: Assign queue entries to sales team member
    Given there are qualified entries in the handoff queue
    And a sales team member has available capacity
    When I assign multiple entries to the sales team member
    Then the entries should be marked as assigned
    And the sales team member's capacity should be updated
    And assignment history should be recorded

  Scenario: Prevent assignment when capacity is exceeded
    Given there are qualified entries in the handoff queue
    And a sales team member is at full capacity
    When I try to assign entries to the sales team member
    Then the assignment should be rejected
    And an error message should indicate capacity exceeded

  Scenario: View queue entry details
    Given there is a qualified entry in the handoff queue
    When I request the entry details
    Then I should see business information
    And qualification criteria details
    And engagement analytics summary
    And qualification scoring breakdown

  Scenario: Bulk qualification with engagement requirements
    Given I have businesses with different engagement levels
    And qualification criteria requiring minimum page views
    When I perform bulk qualification
    Then only businesses with sufficient engagement should qualify
    And engagement data should be included in qualification details

  Scenario: Priority calculation for qualified leads
    Given I have businesses with different scores and engagement
    When they are qualified for handoff
    Then higher scoring businesses should get higher priority
    And businesses with conversions should get priority boost
    And businesses with high page views should get priority boost

  Scenario: Analytics summary for handoff queue
    Given there are entries in various queue statuses
    And some entries are assigned to different sales team members
    When I request the analytics summary
    Then I should see total counts by status
    And assignment breakdown by sales team member
    And qualification criteria breakdown
    And average scores and priorities

  Scenario: Create custom qualification criteria
    Given I want to create new qualification criteria
    When I specify the criteria parameters
    And include required fields and custom rules
    Then the criteria should be created successfully
    And available for use in bulk qualification

  Scenario: Track bulk operation status
    Given I start a bulk qualification operation
    When I check the operation status
    Then I should see the current progress
    And counts of successful and failed qualifications
    And detailed operation results when completed
