Feature: Enhanced Analytics Dashboard UI
  As a system administrator
  I want to view comprehensive analytics through a web dashboard
  So that I can monitor system performance and manage business data

  Background:
    Given the enhanced dashboard web interface is available
    And there is log and business data in the system

  Scenario: View dashboard overview
    When I navigate to the enhanced dashboard page
    Then I should see the analytics header
    And I should see overview statistics cards
    And I should see log types distribution chart
    And I should see activity timeline chart
    And I should see storage insights

  Scenario: Load overview statistics
    Given I am on the enhanced dashboard page
    When the page loads
    Then I should see total logs count
    And I should see total businesses count
    And I should see LLM logs count
    And I should see HTML logs count
    And all statistics should display numerical values

  Scenario: Filter by time range
    Given I am on the enhanced dashboard page
    When I select "Last 24 Hours" from the time range filter
    And I click the refresh button
    Then the statistics should update to reflect the time range
    And charts should show data for the selected period
    When I select "Last 30 Days" from the time range filter
    And I click the refresh button
    Then the data should update to show 30-day statistics

  Scenario: Custom date range selection
    Given I am on the enhanced dashboard page
    When I select "Custom Range" from the time range filter
    Then I should see start date and end date inputs
    When I select a custom start date and end date
    And I click the refresh button
    Then the data should reflect the custom date range

  Scenario: Filter by specific business
    Given I am on the enhanced dashboard page
    When I select a specific business from the business filter
    And I click the refresh button
    Then the analytics should show data only for that business
    And the charts should update to reflect business-specific data

  Scenario: View log types distribution chart
    Given I am on the enhanced dashboard page
    When the page loads
    Then I should see a doughnut chart showing log types
    And the chart should show LLM logs and HTML logs proportions
    And the legend should be clearly labeled
    And hovering over sections should show detailed information

  Scenario: View activity timeline chart
    Given I am on the enhanced dashboard page
    When the page loads
    Then I should see a line chart showing activity over time
    And the chart should show trends for LLM and HTML logs
    And the x-axis should show time periods
    And the y-axis should show log counts
    And the chart should be interactive

  Scenario: View business activity table
    Given I am on the enhanced dashboard page
    When I scroll to the business activity section
    Then I should see a table of top active businesses
    And each row should show business name, total logs, LLM logs, HTML logs
    And each row should show an activity progress bar
    And each row should show last activity timestamp
    And businesses should be sorted by activity level

  Scenario: Refresh dashboard data
    Given I am on the enhanced dashboard page
    When I click the refresh button
    Then all statistics should reload
    And all charts should refresh
    And the business activity table should update
    And loading indicators should be shown during refresh

  Scenario: View storage insights
    Given I am on the enhanced dashboard page
    When I view the storage insights card
    Then I should see average log size
    And I should see largest log size
    And I should see first log date
    And I should see latest log date
    And all sizes should be formatted in appropriate units (B, KB, MB)

  Scenario: Business management section
    Given I am on the enhanced dashboard page
    When I scroll to the business management section
    Then I should see business search functionality
    And I should see archived filter options
    And I should see a business list table
    And I should see pagination controls

  Scenario: Search businesses
    Given I am on the enhanced dashboard page
    When I enter "Restaurant" in the business search field
    Then the business table should filter to show only restaurants
    And the search should be case-insensitive
    And results should update as I type

  Scenario: Filter archived businesses
    Given I am on the enhanced dashboard page
    When I select "Archived Only" from the archived filter
    Then I should only see archived businesses
    And each archived business should show its archive reason
    When I select "Active Only" from the archived filter
    Then I should only see active businesses

  Scenario: Select businesses for bulk actions
    Given I am on the enhanced dashboard page
    When I select individual businesses using checkboxes
    Then the selected businesses should be highlighted
    And the bulk reject button should show the count
    When I select the "select all" checkbox
    Then all visible businesses should be selected

  Scenario: Bulk reject businesses
    Given I am on the enhanced dashboard page
    And I have selected multiple businesses
    When I click the "Reject Selected" button
    Then I should see a confirmation dialog
    When I confirm the rejection
    Then the businesses should be archived
    And I should see a success message
    And the business list should refresh

  Scenario: Individual business actions
    Given I am on the enhanced dashboard page
    When I view the business table
    Then active businesses should show an "Archive" button
    And archived businesses should show a "Restore" button
    When I click "Archive" for a business
    Then I should see a confirmation dialog
    When I confirm the action
    Then the business should be archived

  Scenario: Restore archived businesses
    Given I am on the enhanced dashboard page
    And I am viewing archived businesses
    When I click "Restore" for an archived business
    Then I should see a confirmation dialog
    When I confirm the restoration
    Then the business should become active again
    And the archive reason should be cleared

  Scenario: Business pagination
    Given I am on the enhanced dashboard page
    And there are more businesses than fit on one page
    When I click the "Next" button
    Then I should see the next page of businesses
    And the page indicator should update
    And the "Previous" button should become enabled
    When I click the "Previous" button
    Then I should see the previous page

  Scenario: Business table information
    Given I am on the enhanced dashboard page
    When I view the business table
    Then each business should show name, address, city, state
    And websites should be clickable links
    And scores should be displayed
    And status should show as "Active" or "Archived"
    And archive reasons should be shown for archived businesses

  Scenario: Charts responsiveness
    Given I am on the enhanced dashboard page
    When I resize the browser window
    Then all charts should resize appropriately
    And chart labels should remain readable
    And legends should adjust to the available space

  Scenario: Mobile responsive design
    Given I am on the enhanced dashboard page
    When I resize the browser to mobile width
    Then the dashboard should adapt to mobile layout
    And statistics cards should stack vertically
    And charts should scale to fit mobile screens
    And tables should become horizontally scrollable
    And all controls should remain accessible

  Scenario: Dashboard performance
    Given I am on the enhanced dashboard page
    And there is a large amount of data
    When I perform various operations
    Then the dashboard should load within 5 seconds
    And chart rendering should be smooth
    And table operations should respond within 2 seconds
    And data refreshes should provide loading feedback

  Scenario: Error handling
    Given I am on the enhanced dashboard page
    When there is an error loading data
    Then I should see appropriate error messages
    And the interface should remain functional
    And I should be able to retry failed operations

  Scenario: Auto-refresh functionality
    Given I am on the enhanced dashboard page
    When I enable auto-refresh (if available)
    Then the dashboard should periodically update
    And I should see visual indicators of refresh
    And my current filters and selections should be preserved

  Scenario: Data export functionality
    Given I am on the enhanced dashboard page
    When I view charts and tables
    Then I should be able to interact with chart data
    And business data should be sortable by columns
    And I should be able to see detailed information when needed
