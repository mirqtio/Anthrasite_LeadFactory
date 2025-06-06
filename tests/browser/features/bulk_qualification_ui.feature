Feature: Bulk Lead Qualification UI
  As a sales manager
  I want to qualify multiple leads through a web interface
  So that I can efficiently manage the lead qualification process

  Background:
    Given the bulk qualification web interface is available
    And there are sample businesses in the system
    And qualification criteria are configured

  Scenario: View bulk qualification dashboard
    When I navigate to the bulk qualification page
    Then I should see the qualification controls
    And I should see the business list table
    And I should see filter and search options
    And I should see the qualification criteria dropdown

  Scenario: Load qualification criteria
    Given I am on the bulk qualification page
    When the page loads
    Then the qualification criteria dropdown should be populated
    And each criteria should show its minimum score requirement
    And the qualify button should be initially disabled

  Scenario: Filter businesses by score
    Given I am on the bulk qualification page
    When I set the minimum score to "80"
    Then I should only see businesses with score 80 or higher
    And the business count should be updated accordingly

  Scenario: Filter businesses by type
    Given I am on the bulk qualification page
    When I select "high_score" from the business filter
    Then I should only see high-scoring businesses
    And the table should refresh automatically

  Scenario: Search businesses by name
    Given I am on the bulk qualification page
    When I search for "Restaurant"
    Then I should only see businesses with "Restaurant" in the name
    And the search should be case-insensitive
    And results should update as I type

  Scenario: Search businesses by email
    Given I am on the bulk qualification page
    When I search for "test@restaurant.com"
    Then I should see the business with that email address
    And other businesses should be filtered out

  Scenario: Sort businesses by score
    Given I am on the bulk qualification page
    When I select "Score (High to Low)" from the sort dropdown
    Then businesses should be sorted by score in descending order
    And the highest scoring business should appear first

  Scenario: Sort businesses by name
    Given I am on the bulk qualification page
    When I select "Name (A-Z)" from the sort dropdown
    Then businesses should be sorted alphabetically by name
    And names starting with A should appear first

  Scenario: Select individual businesses
    Given I am on the bulk qualification page
    When I select a business with high score
    Then the business should be highlighted as selected
    And the selected count should increment
    And the qualify button should remain disabled until criteria is selected

  Scenario: Select all visible businesses
    Given I am on the bulk qualification page
    When I click the "Select All Visible" button
    Then all visible businesses should be selected
    And the selected count should show the total number
    And the select all checkbox should be checked

  Scenario: Clear business selection
    Given I am on the bulk qualification page
    And I have selected multiple businesses
    When I click the "Clear Selection" button
    Then no businesses should be selected
    And the selected count should show "0 selected"
    And the qualify button should be disabled

  Scenario: Enable qualify button with criteria and selection
    Given I am on the bulk qualification page
    When I select a qualification criteria
    And I select one or more businesses
    Then the qualify button should become enabled
    And it should show "Qualify Selected"

  Scenario: Start bulk qualification process
    Given I am on the bulk qualification page
    And I have selected qualification criteria "High Value Lead"
    And I have selected 3 businesses
    When I click the qualify button
    Then the qualification modal should open
    And it should show the count of businesses being qualified
    And it should show the selected criteria name

  Scenario: Monitor qualification progress
    Given I am performing bulk qualification
    When the qualification process is running
    Then I should see a progress bar
    And I should see status updates like "Processing... (2/3)"
    And the progress should update in real-time

  Scenario: Complete qualification process
    Given I am performing bulk qualification
    When the qualification process completes
    Then I should see completion results
    And it should show qualified count, rejected count, and insufficient data count
    And I should see a success message
    And the business list should refresh to show updated statuses

  Scenario: Handle qualification errors
    Given I am performing bulk qualification
    When there is an error in the qualification process
    Then I should see an error message
    And the modal should show the error details
    And I should be able to close the modal

  Scenario: Filter by business category
    Given I am on the bulk qualification page
    When I filter by category "restaurant"
    Then I should only see restaurant businesses
    And the filter should work with other filters

  Scenario: Refresh business data
    Given I am on the bulk qualification page
    When I click the refresh button
    Then the business list should reload
    And any applied filters should remain active
    And selected businesses should be cleared

  Scenario: Navigate to handoff queue
    Given I am on the bulk qualification page
    When I click the "View Handoff Queue" link
    Then I should be navigated to the handoff queue page
    And the page should load successfully

  Scenario: Pagination of business list
    Given I am on the bulk qualification page
    And there are more businesses than fit on one page
    When I navigate through pages
    Then I should see different sets of businesses
    And page navigation should work correctly
    And my selection should persist across pages

  Scenario: Business details display
    Given I am on the bulk qualification page
    When I view the business table
    Then each business should show name, email, website, category, and score
    And scores should be color-coded (high=green, medium=yellow, low=red)
    And status badges should be properly styled
    And websites should be clickable links

  Scenario: Responsive design for mobile
    Given I am on the bulk qualification page
    When I resize the browser to mobile width
    Then the interface should adapt to mobile layout
    And controls should stack vertically
    And the table should become horizontally scrollable
    And all functionality should remain accessible

  Scenario: Performance with large datasets
    Given I am on the bulk qualification page
    And there are many businesses in the system
    When I perform filtering and sorting operations
    Then the interface should respond within 2 seconds
    And pagination should load quickly
    And search should provide immediate feedback
