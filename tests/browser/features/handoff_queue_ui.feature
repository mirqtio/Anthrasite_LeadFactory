Feature: Handoff Queue UI
  As a sales team manager
  I want to manage qualified leads through a handoff queue interface
  So that I can efficiently assign leads to sales team members

  Background:
    Given the handoff queue web interface is available
    And there are qualified leads in the handoff queue
    And sales team members are configured

  Scenario: View handoff queue dashboard
    When I navigate to the handoff queue page
    Then I should see the queue statistics
    And I should see total, unassigned, assigned, and contacted counts
    And I should see the queue entries table
    And I should see assignment controls

  Scenario: View queue statistics
    Given I am on the handoff queue page
    When the page loads
    Then I should see real-time statistics
    And total queue entries should be displayed
    And unassigned entries count should be shown
    And assigned entries count should be shown
    And contacted entries count should be shown

  Scenario: Filter queue by status
    Given I am on the handoff queue page
    When I select "qualified" from the status filter
    Then I should only see qualified entries
    And the queue count should update accordingly
    When I select "assigned" from the status filter
    Then I should only see assigned entries

  Scenario: Filter queue by assignee
    Given I am on the handoff queue page
    And there are entries assigned to different sales members
    When I select a specific assignee from the filter
    Then I should only see entries assigned to that person
    And the filter should show current capacity information

  Scenario: Filter by minimum priority
    Given I am on the handoff queue page
    When I set minimum priority to "70"
    Then I should only see entries with priority 70 or higher
    And lower priority entries should be hidden

  Scenario: Load sales team members
    Given I am on the handoff queue page
    When the page loads
    Then the assign to dropdown should be populated with sales team members
    And each member should show their current capacity (e.g., "John Doe (3/10)")
    And members at full capacity should be disabled
    And inactive members should not be shown

  Scenario: Select individual queue entries
    Given I am on the handoff queue page
    When I select a queue entry
    Then the entry should be highlighted as selected
    And the selected count should increment
    And the assign button should remain disabled until a sales member is selected

  Scenario: Select all visible entries
    Given I am on the handoff queue page
    When I click the "Select All Visible" button
    Then all visible queue entries should be selected
    And the selected count should show the total number
    And the select all checkbox should be checked

  Scenario: Clear entry selection
    Given I am on the handoff queue page
    And I have selected multiple queue entries
    When I click the "Clear Selection" button
    Then no entries should be selected
    And the selected count should show "0 selected"
    And the assign button should be disabled

  Scenario: Enable assign button with selection and assignee
    Given I am on the handoff queue page
    When I select one or more queue entries
    And I select a sales team member from the dropdown
    Then the assign button should become enabled
    And it should show "Assign Selected"

  Scenario: Start bulk assignment process
    Given I am on the handoff queue page
    And I have selected 3 queue entries
    And I have selected sales member "John Doe"
    When I click the assign button
    Then the assignment modal should open
    And it should show the count of entries being assigned
    And it should show the assignee name

  Scenario: Monitor assignment progress
    Given I am performing bulk assignment
    When the assignment process is running
    Then I should see a processing status
    And the modal should show "Processing assignment..."
    And the operation should complete quickly

  Scenario: Complete assignment process
    Given I am performing bulk assignment
    When the assignment process completes
    Then I should see completion results
    And it should show processed count, successful count, and failed count
    And I should see a success message
    And the queue should refresh to show updated assignments

  Scenario: Handle assignment errors
    Given I am performing bulk assignment
    When there is an error in the assignment process
    Then I should see an error message
    And the modal should show the error details
    And I should be able to close the modal and retry

  Scenario: View entry details
    Given I am on the handoff queue page
    When I click the view button for a queue entry
    Then the entry details modal should open
    And I should see complete business information
    And I should see qualification information
    And I should see assignment information if assigned
    And I should see any notes or comments

  Scenario: Queue entry information display
    Given I am on the handoff queue page
    When I view the queue table
    Then each entry should show business name and email
    And qualification score should be displayed with color coding
    And priority should be shown with appropriate styling
    And status should be displayed with colored badges
    And assigned person should be shown or "Unassigned"
    And qualification date should be displayed

  Scenario: Priority and score color coding
    Given I am on the handoff queue page
    When I view queue entries
    Then high scores (80+) should be shown in green
    And medium scores (50-79) should be shown in yellow
    And low scores (<50) should be shown in red
    And high priority entries should be highlighted
    And critical priority entries should stand out

  Scenario: Refresh queue data
    Given I am on the handoff queue page
    When I click the refresh button
    Then the queue data should reload
    And statistics should be updated
    And sales team information should be refreshed
    And any applied filters should remain active

  Scenario: Navigate to bulk qualification
    Given I am on the handoff queue page
    When I click the "Bulk Qualification" link
    Then I should be navigated to the bulk qualification page
    And the page should load successfully

  Scenario: Pagination of queue entries
    Given I am on the handoff queue page
    And there are more entries than fit on one page
    When I navigate through pages
    Then I should see different sets of entries
    And page navigation should work correctly
    And my selection should be cleared when changing pages

  Scenario: Assignment capacity management
    Given I am on the handoff queue page
    When I view the sales member dropdown
    Then members should show their current capacity
    And members at full capacity should be disabled
    And I should not be able to assign to disabled members
    When a member reaches capacity
    Then they should automatically become disabled

  Scenario: Real-time updates
    Given I am on the handoff queue page
    When queue entries are updated by other users
    Then the statistics should update automatically
    And the queue list should reflect changes
    And I should see updated assignment information

  Scenario: Responsive design for mobile
    Given I am on the handoff queue page
    When I resize the browser to mobile width
    Then the interface should adapt to mobile layout
    And statistics should stack vertically
    And the table should become horizontally scrollable
    And all controls should remain accessible

  Scenario: Performance with large queue
    Given I am on the handoff queue page
    And there are many entries in the queue
    When I perform filtering and sorting operations
    Then the interface should respond within 2 seconds
    And pagination should load quickly
    And assignment operations should provide progress feedback
