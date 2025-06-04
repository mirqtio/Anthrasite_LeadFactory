Feature: Analytics Dashboard
  As a system administrator
  I want to view analytics and insights about log data
  So that I can understand system usage patterns and performance

  Background:
    Given the analytics dashboard is running
    And the database contains varied log data
    And I am on the analytics dashboard page

  Scenario: View the main dashboard
    When I load the analytics dashboard page
    Then I should see the page title "Analytics Dashboard"
    And I should see overview statistics cards
    And I should see interactive charts
    And I should see the top businesses table
    And I should see filter controls

  Scenario: View overview statistics
    When I load the dashboard
    Then I should see the total logs count
    And I should see the total businesses count
    And I should see LLM logs count
    And I should see HTML logs count
    And all statistics should display actual numbers

  Scenario: View log type distribution chart
    When I view the log types chart
    Then I should see a pie chart showing log distribution
    And the chart should show percentages for each log type
    And the legend should display log type names
    And colors should be distinct for each type

  Scenario: View activity timeline chart
    When I view the activity timeline
    Then I should see a line chart showing activity over time
    And the chart should show separate lines for different log types
    And the x-axis should show time periods
    And the y-axis should show log counts

  Scenario: View top businesses table
    When I view the businesses section
    Then I should see a table of top active businesses
    And each row should show business name and log counts
    And logs should be broken down by type
    And businesses should be sorted by total activity
    And I should see progress bars indicating relative activity

  Scenario: Filter by time range
    When I select "Last 24 Hours" from the time range filter
    And I click the refresh button
    Then all charts should update to show 24-hour data
    And statistics should reflect the time filter
    And the date range should be clearly indicated

  Scenario: Filter by business
    When I select a specific business from the business filter
    And I click the refresh button
    Then all data should be filtered to that business only
    And charts should show data for the selected business
    And statistics should reflect the business filter

  Scenario: Use custom date range
    When I select "Custom Range" from the time filter
    Then I should see start and end date fields
    When I set a custom date range
    And I click refresh
    Then data should be filtered to the custom range
    And the date range should be displayed in the interface

  Scenario: Real-time data updates
    When I view the dashboard
    And data changes in the system
    And I click the refresh button
    Then charts should update with new data
    And statistics should reflect current state
    And changes should be visually apparent

  Scenario: Interactive chart features
    When I hover over chart elements
    Then I should see tooltips with detailed information
    And hover effects should provide additional context
    When I click on chart legends
    Then I should be able to toggle data series visibility

  Scenario: Navigate back to logs browser
    When I click the "Logs Browser" breadcrumb link
    Then I should be taken to the logs browser page
    And the navigation should work seamlessly

  Scenario: Storage insights section
    When I view the storage insights
    Then I should see average log size information
    And I should see largest log size
    And I should see date range of stored logs
    And I should see first and latest log dates

  Scenario: Business activity analysis
    When I examine the business activity table
    Then I should see accurate log counts per business
    And I should see the last activity timestamp
    And I should see progress indicators for relative activity
    And the data should be sortable by different columns

  Scenario: Performance metrics
    When I view performance indicators
    Then I should see cache hit/miss ratios if available
    And I should see data loading times
    And I should see system performance indicators

  Scenario: Responsive dashboard design
    Given I am viewing the dashboard on different screen sizes
    When I resize the browser window
    Then charts should resize appropriately
    And the layout should adapt to the screen size
    And all information should remain accessible
    And touch interactions should work on mobile devices

  Scenario: Export dashboard data
    When I attempt to export dashboard data
    Then I should be able to save chart data
    And I should be able to export statistics
    And exported data should be in a useful format

  Scenario: Filter combinations
    When I select a time range AND a specific business
    Then all visualizations should reflect both filters
    And the data should be consistently filtered across all elements
    And the filters should work together correctly

  Scenario: Error handling in dashboard
    Given there are API connectivity issues
    When I try to load dashboard data
    Then I should see appropriate error messages
    And the dashboard should gracefully handle missing data
    And I should be able to retry loading data

  Scenario: Chart interactions
    When I interact with the activity timeline chart
    Then I should be able to zoom in on time periods
    And I should be able to see detailed data points
    When I interact with the pie chart
    Then I should see specific percentages and counts

  Scenario: Dashboard performance
    Given there are large amounts of log data
    When I load the dashboard
    Then charts should render within acceptable time
    And interactions should remain responsive
    And the browser should not become unresponsive

  Scenario: Data accuracy verification
    When I view statistics on the dashboard
    Then the numbers should match the actual data
    And totals should add up correctly
    And percentages should be mathematically accurate
    And date ranges should be properly calculated

  Scenario: Accessibility features
    When I navigate the dashboard with keyboard only
    Then all interactive elements should be accessible
    And I should be able to view all data without a mouse
    And screen readers should be able to interpret the content
    And color contrast should meet accessibility standards

  Scenario: Multi-user dashboard usage
    Given multiple users are viewing the dashboard
    When one user changes filters
    Then other users should not be affected
    And each user should maintain independent state
    And concurrent usage should not cause conflicts

  Scenario: Dashboard refresh functionality
    When I click the refresh button
    Then all data should be reloaded from the server
    And charts should update with current information
    And any applied filters should be maintained
    And the refresh should complete within reasonable time

  Scenario: Bookmark dashboard views
    Given I have applied specific filters
    When I bookmark the dashboard URL
    And I return to the bookmark later
    Then the same filters should be applied
    And the same view should be restored

  Scenario: Integration with logs browser
    When I view business data in the dashboard
    And I want to see detailed logs for a business
    Then I should be able to navigate to filtered logs
    And the context should be preserved between applications
