Feature: Logs Browser Interface
  As a system administrator
  I want to browse and analyze HTML and LLM logs
  So that I can monitor system performance and troubleshoot issues

  Background:
    Given the logs web interface is running
    And the database contains sample log data
    And I am on the logs browser page

  Scenario: View the main logs interface
    When I load the logs browser page
    Then I should see the page title "Logs Browser"
    And I should see the navigation sidebar
    And I should see the logs table with headers
    And I should see pagination controls
    And I should see filter controls

  Scenario: Browse all logs by default
    When I load the logs browser page
    Then I should see logs from all types displayed
    And the "All Logs" navigation item should be active
    And the total count should show all available logs
    And logs should be sorted by timestamp in descending order

  Scenario: Filter logs by type using navigation
    When I click on the "LLM Logs" navigation item
    Then only LLM logs should be displayed
    And the log type filter should show "llm"
    And the "LLM Logs" navigation item should be active
    And the filtered count should update accordingly

  Scenario: Filter logs by type using dropdown
    When I select "raw_html" from the log type filter
    And I click the search button
    Then only HTML logs should be displayed
    And all visible log entries should have type "raw_html"
    And the results count should reflect the filtered data

  Scenario: Filter logs by business ID
    When I enter "123" in the business ID filter
    And I click the search button
    Then only logs for business ID 123 should be displayed
    And all visible log entries should show business ID 123
    And the results count should update

  Scenario: Search logs by content
    When I enter "marketing" in the search box
    And I click the search button
    Then only logs containing "marketing" should be displayed
    And the search query should be highlighted in results
    And the search statistics should show the query

  Scenario: Combine multiple filters
    When I select "llm" from the log type filter
    And I enter "1" in the business ID filter
    And I enter "content" in the search box
    And I click the search button
    Then logs should be filtered by all criteria
    And only LLM logs for business 1 containing "content" should show
    And the results count should reflect multiple filters

  Scenario: Clear all filters
    Given I have applied multiple filters
    When I click the clear filters button
    Then all filter fields should be empty
    And the "All Logs" navigation should be active
    And all logs should be displayed again
    And the total count should be restored

  Scenario: Navigate through pages
    Given there are more logs than fit on one page
    When I click the "Next" page button
    Then I should see the next page of results
    And the page indicator should update
    And different log entries should be displayed
    And the "Previous" button should become enabled

  Scenario: View detailed log information
    When I click the "View" button for a log entry
    Then a modal dialog should open
    And I should see detailed log information
    And I should see the full log content
    And I should see metadata information
    And I should be able to close the modal

  Scenario: Access statistics
    When I click on the "Statistics" navigation item
    Then a statistics modal should open
    And I should see total log counts
    And I should see logs by type breakdown
    And I should see top businesses by log count
    And I should see date range information

  Scenario: Export logs as CSV
    When I click the export button
    Then a CSV file should be downloaded
    And the filename should contain the current date
    And the file should contain log data in CSV format

  Scenario: Export filtered logs
    Given I have filtered logs by type "llm"
    When I click the export button
    Then only LLM logs should be exported
    And the exported data should match the filtered view

  Scenario: View real-time statistics
    When I apply filters to the logs
    Then the statistics counters should update automatically
    And the filtered count should reflect current results
    And the selected type indicator should update

  Scenario: Navigate to analytics dashboard
    When I click on the "Dashboard" navigation item
    Then a new tab should open with the analytics dashboard
    And I should see charts and visualizations
    And I should see performance metrics

  Scenario: Responsive design on mobile
    Given I am viewing the page on a mobile device
    When I load the logs browser page
    Then the interface should adapt to the smaller screen
    And navigation should remain accessible
    And tables should be scrollable horizontally
    And filters should be usable on touch devices

  Scenario: Handle errors gracefully
    Given the API returns an error
    When I try to load logs
    Then I should see an appropriate error message
    And the interface should remain functional
    And I should be able to retry the operation

  Scenario: Search with no results
    When I search for "nonexistentterm"
    Then I should see a "no results found" message
    And the results count should show zero
    And I should be able to clear the search

  Scenario: Sort logs by different columns
    When I click on the business ID column header
    Then logs should be sorted by business ID
    And the sort indicator should show ascending order
    When I click the same header again
    Then logs should be sorted in descending order

  Scenario: Pagination with filters
    Given I have applied filters that return many results
    When I navigate through filtered pages
    Then each page should show filtered results only
    And the total count should reflect filtered data
    And pagination should work correctly with filters

  Scenario: Auto-refresh functionality
    Given I am viewing the logs
    When new logs are added to the system
    And I refresh the page
    Then I should see the updated log count
    And new logs should appear in the list

  Scenario: Bookmark filtered view
    Given I have applied specific filters
    When I bookmark the current URL
    And I navigate away and return using the bookmark
    Then the same filters should be applied
    And the same filtered results should be displayed

  Scenario: Keyboard navigation
    When I use tab to navigate through the interface
    Then I should be able to reach all interactive elements
    And the focus should be clearly visible
    And I should be able to activate controls with Enter/Space

  Scenario: Performance with large datasets
    Given there are thousands of log entries
    When I load the logs browser
    Then the page should load within acceptable time
    And pagination should handle large datasets efficiently
    And filtering should remain responsive

  Scenario: Cache performance indicators
    When I navigate between filtered views
    Then subsequent loads should be faster due to caching
    And I should be able to view cache statistics
    And cache hit/miss ratios should be displayed

  Scenario: Export with custom options
    When I click the export button
    And I select "include content" option
    And I choose JSON format
    Then the export should include full content
    And the file should be in JSON format
    And the export should complete successfully

  Scenario: Multiple browser tabs
    Given I have the logs browser open in multiple tabs
    When I perform actions in one tab
    Then other tabs should not interfere
    And each tab should maintain its own state
    And exports from different tabs should work independently
