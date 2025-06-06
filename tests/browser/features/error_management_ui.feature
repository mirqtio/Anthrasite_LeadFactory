Feature: Error Management UI
  As a system administrator
  I want to manage pipeline errors through a web interface
  So that I can efficiently handle error resolution and bulk operations

  Background:
    Given the error management web interface is available
    And there are sample errors in the system

  Scenario: View error management dashboard
    When I navigate to the error management page
    Then I should see the error dashboard metrics
    And I should see the error list table
    And I should see filter controls

  Scenario: Filter errors by severity
    Given I am on the error management page
    When I select "critical" from the severity filter
    And I click apply filters
    Then I should only see critical errors in the table
    And the error count should be updated

  Scenario: Filter errors by category
    Given I am on the error management page
    When I select "network" from the category filter
    And I click apply filters
    Then I should only see network category errors
    And the metrics should reflect the filtered data

  Scenario: Filter errors by pipeline stage
    Given I am on the error management page
    When I select "scrape" from the stage filter
    And I click apply filters
    Then I should only see scrape stage errors

  Scenario: Select individual errors
    Given I am on the error management page
    When I select an error with ID "err-001"
    Then the error should be highlighted as selected
    And the selected count should show "1 selected"
    And bulk actions should become visible

  Scenario: Select all errors
    Given I am on the error management page
    When I click the select all checkbox
    Then all visible errors should be selected
    And the selected count should reflect all errors
    And bulk actions should be visible

  Scenario: Bulk dismiss errors
    Given I am on the error management page
    And I have selected multiple errors
    When I click the bulk dismiss button
    Then the bulk dismiss modal should open
    When I select "resolved_manually" as the dismissal reason
    And I add a comment "Resolved during maintenance"
    And I submit the bulk dismiss form
    Then the errors should be dismissed successfully
    And I should see a success message
    And the error list should be refreshed

  Scenario: Bulk fix errors
    Given I am on the error management page
    And I have selected errors that can be auto-fixed
    When I click the bulk fix button
    Then the bulk fix modal should open
    When I set max fix attempts to "3"
    And I submit the bulk fix form
    Then the fix process should start
    And I should see progress updates
    And eventually see completion results

  Scenario: Bulk categorize errors
    Given I am on the error management page
    And I have selected multiple errors
    When I click the bulk categorize button
    Then the bulk categorize modal should open
    When I select "database" as the new category
    And I select "high" as the new severity
    And I add tags "urgent, investigate"
    And I submit the categorization
    Then the errors should be updated successfully
    And the error list should reflect the changes

  Scenario: Reset filters
    Given I am on the error management page
    And I have applied multiple filters
    When I click the reset filters button
    Then all filters should be cleared
    And the full error list should be displayed
    And metrics should show total counts

  Scenario: Pagination of error list
    Given I am on the error management page
    And there are more errors than fit on one page
    When I click the next page button
    Then I should see the next set of errors
    And the page indicator should update
    When I click the previous page button
    Then I should see the previous set of errors

  Scenario: View error details
    Given I am on the error management page
    When I click the view button for error "err-001"
    Then I should see detailed error information
    And the error stack trace should be displayed
    And related business information should be shown

  Scenario: Real-time error updates
    Given I am on the error management page
    When new errors are added to the system
    Then the dashboard metrics should update automatically
    And the error count should reflect new errors

  Scenario: Mobile responsive design
    Given I am on the error management page
    When I resize the browser to mobile width
    Then the interface should adapt to mobile layout
    And all functionality should remain accessible
    And tables should become horizontally scrollable

  Scenario: Error management performance
    Given I am on the error management page
    And there are many errors in the system
    When I perform filter operations
    Then the interface should respond within 2 seconds
    And pagination should load quickly
    And bulk operations should provide progress feedback
