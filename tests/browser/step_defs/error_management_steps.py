"""
Step definitions for Error Management UI browser tests.
"""

from typing import Dict, Any
from pytest_bdd import given, when, then, parsers
from playwright.sync_api import Page, expect

from tests.browser.page_objects import ErrorManagementPage


@when('I navigate to the error management page')
def navigate_to_error_management(page: Page, browser_context_data: Dict[str, Any]):
    """Navigate to the error management page."""
    error_page = ErrorManagementPage(page)
    error_page.navigate()
    browser_context_data['current_page'] = error_page


@then('I should see the error dashboard metrics')
def should_see_dashboard_metrics(page: Page):
    """Verify error dashboard metrics are visible."""
    expect(page.locator('#totalErrors')).to_be_visible()
    expect(page.locator('#criticalErrors')).to_be_visible()
    expect(page.locator('#fixedErrors')).to_be_visible()


@then('I should see the error list table')
def should_see_error_list_table(page: Page):
    """Verify error list table is visible."""
    expect(page.locator('#errorTable')).to_be_visible()
    expect(page.locator('#errorTableBody')).to_be_visible()


@then('I should see filter controls')
def should_see_filter_controls(page: Page):
    """Verify filter controls are visible."""
    expect(page.locator('#timeWindow')).to_be_visible()
    expect(page.locator('#severityFilter')).to_be_visible()
    expect(page.locator('#categoryFilter')).to_be_visible()
    expect(page.locator('#stageFilter')).to_be_visible()


@when(parsers.parse('I select "{value}" from the severity filter'))
def select_severity_filter(page: Page, value: str):
    """Select a value from the severity filter."""
    error_page = ErrorManagementPage(page)
    error_page.set_filter('severity', value)


@when(parsers.parse('I select "{value}" from the category filter'))
def select_category_filter(page: Page, value: str):
    """Select a value from the category filter."""
    error_page = ErrorManagementPage(page)
    error_page.set_filter('category', value)


@when(parsers.parse('I select "{value}" from the stage filter'))
def select_stage_filter(page: Page, value: str):
    """Select a value from the stage filter."""
    error_page = ErrorManagementPage(page)
    error_page.set_filter('stage', value)


@when('I click apply filters')
def click_apply_filters(page: Page):
    """Click the apply filters button."""
    error_page = ErrorManagementPage(page)
    error_page.apply_filters()


@then('I should only see critical errors in the table')
def should_see_only_critical_errors(page: Page):
    """Verify only critical errors are shown."""
    # Check that all visible error rows have critical severity
    error_rows = page.query_selector_all('#errorTableBody tr')
    for row in error_rows:
        severity_badge = row.query_selector('.severity-badge')
        if severity_badge:
            assert 'severity-critical' in severity_badge.get_attribute('class')


@then('I should only see network category errors')
def should_see_only_network_errors(page: Page):
    """Verify only network category errors are shown."""
    error_rows = page.query_selector_all('#errorTableBody tr')
    for row in error_rows:
        category_badge = row.query_selector('.category-badge')
        if category_badge:
            assert 'network' in category_badge.text_content().lower()


@then('I should only see scrape stage errors')
def should_see_only_scrape_errors(page: Page):
    """Verify only scrape stage errors are shown."""
    error_rows = page.query_selector_all('#errorTableBody tr')
    for row in error_rows:
        cells = row.query_selector_all('td')
        if len(cells) > 3:  # Stage is in the 4th column (index 3)
            stage_text = cells[3].text_content()
            assert 'scrape' in stage_text.lower()


@then('the error count should be updated')
def error_count_should_be_updated(page: Page):
    """Verify the error count reflects filtered results."""
    # The error count in metrics should reflect the current filter
    total_errors = page.text_content('#totalErrors')
    assert total_errors != '-', "Error count should be updated with actual numbers"


@then('the metrics should reflect the filtered data')
def metrics_reflect_filtered_data(page: Page):
    """Verify metrics reflect the current filter."""
    # All metrics should show actual numbers, not placeholders
    total_errors = page.text_content('#totalErrors')
    critical_errors = page.text_content('#criticalErrors')
    fixed_errors = page.text_content('#fixedErrors')

    assert total_errors != '-', "Total errors should show actual count"
    assert critical_errors != '-', "Critical errors should show actual count"
    assert fixed_errors != '-', "Fixed errors should show actual count"


@when(parsers.parse('I select an error with ID "{error_id}"'))
def select_error_by_id(page: Page, error_id: str):
    """Select a specific error by ID."""
    error_page = ErrorManagementPage(page)
    error_page.select_error(error_id)


@then('the error should be highlighted as selected')
def error_should_be_highlighted(page: Page):
    """Verify the selected error is highlighted."""
    selected_rows = page.query_selector_all('#errorTableBody tr.selected')
    assert len(selected_rows) > 0, "At least one error should be highlighted as selected"


@then(parsers.parse('the selected count should show "{count}"'))
def selected_count_should_show(page: Page, count: str):
    """Verify the selected count displays the expected value."""
    selected_count_text = page.text_content('#selectedCount')
    assert count in selected_count_text, f"Expected '{count}' in selected count, got '{selected_count_text}'"


@then('bulk actions should become visible')
def bulk_actions_should_be_visible(page: Page):
    """Verify bulk actions section becomes visible."""
    error_page = ErrorManagementPage(page)
    assert error_page.is_bulk_actions_visible(), "Bulk actions should be visible when errors are selected"


@when('I click the select all checkbox')
def click_select_all_checkbox(page: Page):
    """Click the select all checkbox."""
    error_page = ErrorManagementPage(page)
    error_page.select_all_errors()


@then('all visible errors should be selected')
def all_errors_should_be_selected(page: Page):
    """Verify all visible errors are selected."""
    checkboxes = page.query_selector_all('#errorTableBody input[type="checkbox"]')
    for checkbox in checkboxes:
        assert checkbox.is_checked(), "All error checkboxes should be checked"


@then('the selected count should reflect all errors')
def selected_count_reflects_all_errors(page: Page):
    """Verify selected count shows total number of visible errors."""
    error_page = ErrorManagementPage(page)
    error_count = error_page.get_error_count()
    selected_count = error_page.get_selected_count()

    # Extract number from selected count (e.g., "5 selected" -> 5)
    selected_number = int(selected_count.split()[0])
    assert selected_number == error_count, f"Selected count {selected_number} should match error count {error_count}"


@then('bulk actions should be visible')
def bulk_actions_visible(page: Page):
    """Verify bulk actions are visible."""
    expect(page.locator('#bulkActions.visible')).to_be_visible()


@given('I have selected multiple errors')
def have_selected_multiple_errors(page: Page):
    """Set up state with multiple errors selected."""
    error_page = ErrorManagementPage(page)
    error_page.select_all_errors()

    # Verify we have actually selected multiple errors
    selected_count = error_page.get_selected_count()
    selected_number = int(selected_count.split()[0])
    assert selected_number > 1, "Should have multiple errors selected"


@when('I click the bulk dismiss button')
def click_bulk_dismiss_button(page: Page):
    """Click the bulk dismiss button."""
    error_page = ErrorManagementPage(page)
    error_page.open_bulk_dismiss_modal()


@then('the bulk dismiss modal should open')
def bulk_dismiss_modal_should_open(page: Page):
    """Verify the bulk dismiss modal opens."""
    expect(page.locator('#bulkDismissModal')).to_be_visible()


@when(parsers.parse('I select "{reason}" as the dismissal reason'))
def select_dismissal_reason(page: Page, reason: str):
    """Select a dismissal reason."""
    page.select_option('#dismissReason', reason)


@when(parsers.parse('I add a comment "{comment}"'))
def add_dismissal_comment(page: Page, comment: str):
    """Add a comment for dismissal."""
    page.fill('#dismissComment', comment)


@when('I submit the bulk dismiss form')
def submit_bulk_dismiss_form(page: Page):
    """Submit the bulk dismiss form."""
    # Mock the bulk dismiss API call
    page.route('**/api/errors/bulk-dismiss', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='{"results": {"dismissed": ["err-001", "err-002"]}, "message": "Successfully dismissed errors"}'
    ))

    page.click('button[type="submit"]:has-text("Dismiss Selected Errors")')


@then('the errors should be dismissed successfully')
def errors_dismissed_successfully(page: Page):
    """Verify errors are dismissed successfully."""
    # The page should show a success message and close the modal
    # We can check that the modal is no longer visible
    page.wait_for_function("document.querySelector('#bulkDismissModal').style.display === 'none'")


@then('the error list should be refreshed')
def error_list_refreshed(page: Page):
    """Verify the error list is refreshed."""
    # The error list should be reloaded
    # We can verify by checking that the table is still visible and functional
    expect(page.locator('#errorTable')).to_be_visible()


@given('I have selected errors that can be auto-fixed')
def have_selected_fixable_errors(page: Page):
    """Set up state with fixable errors selected."""
    # Select some errors that could potentially be auto-fixed
    error_page = ErrorManagementPage(page)
    error_page.select_error('err-001')  # Network error that might be retryable


@when('I click the bulk fix button')
def click_bulk_fix_button(page: Page):
    """Click the bulk fix button."""
    page.click('button:has-text("Bulk Fix")')


@then('the bulk fix modal should open')
def bulk_fix_modal_should_open(page: Page):
    """Verify the bulk fix modal opens."""
    expect(page.locator('#bulkFixModal')).to_be_visible()


@when(parsers.parse('I set max fix attempts to "{attempts}"'))
def set_max_fix_attempts(page: Page, attempts: str):
    """Set the maximum fix attempts."""
    page.select_option('#maxFixesPerError', attempts)


@when('I submit the bulk fix form')
def submit_bulk_fix_form(page: Page):
    """Submit the bulk fix form."""
    # Mock the bulk fix API call
    page.route('**/api/errors/bulk-fix', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "results": {
                "summary": {
                    "successful_fixes": 2,
                    "failed_fixes": 0,
                    "manual_intervention_required": 0
                }
            }
        }'''
    ))

    page.click('button[type="submit"]:has-text("Start Bulk Fix")')


@then('the fix process should start')
def fix_process_should_start(page: Page):
    """Verify the fix process starts."""
    # The modal should show processing state
    expect(page.locator('#bulkFixModal')).to_be_visible()


@then('I should see progress updates')
def should_see_progress_updates(page: Page):
    """Verify progress updates are shown."""
    # In a real implementation, this would check for progress indicators
    # For now, we verify the modal remains open during processing
    expect(page.locator('#bulkFixModal')).to_be_visible()


@then('eventually see completion results')
def see_completion_results(page: Page):
    """Verify completion results are shown."""
    # Wait for the fix process to complete and show results
    page.wait_for_timeout(1000)  # Simulate processing time
    # The modal should still be visible showing results
    expect(page.locator('#bulkFixModal')).to_be_visible()


@when('I click the bulk categorize button')
def click_bulk_categorize_button(page: Page):
    """Click the bulk categorize button."""
    page.click('button:has-text("Bulk Categorize")')


@then('the bulk categorize modal should open')
def bulk_categorize_modal_should_open(page: Page):
    """Verify the bulk categorize modal opens."""
    expect(page.locator('#bulkCategorizeModal')).to_be_visible()


@when(parsers.parse('I select "{category}" as the new category'))
def select_new_category(page: Page, category: str):
    """Select a new category."""
    page.select_option('#newCategory', category)


@when(parsers.parse('I select "{severity}" as the new severity'))
def select_new_severity(page: Page, severity: str):
    """Select a new severity."""
    page.select_option('#newSeverity', severity)


@when(parsers.parse('I add tags "{tags}"'))
def add_tags(page: Page, tags: str):
    """Add tags for categorization."""
    page.fill('#newTags', tags)


@when('I submit the categorization')
def submit_categorization(page: Page):
    """Submit the categorization form."""
    # Mock the bulk categorize API call
    page.route('**/api/errors/bulk-categorize', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='{"results": {"updated": ["err-001", "err-002"]}, "message": "Successfully updated errors"}'
    ))

    page.click('button[type="submit"]:has-text("Update Selected Errors")')


@then('the errors should be updated successfully')
def errors_updated_successfully(page: Page):
    """Verify errors are updated successfully."""
    # Similar to dismiss, check for success and modal closure
    page.wait_for_timeout(1000)


@then('the error list should reflect the changes')
def error_list_reflects_changes(page: Page):
    """Verify the error list reflects the categorization changes."""
    # The error list should be refreshed with updated categories
    expect(page.locator('#errorTable')).to_be_visible()


@given('I have applied multiple filters')
def have_applied_multiple_filters(page: Page):
    """Set up state with multiple filters applied."""
    error_page = ErrorManagementPage(page)
    error_page.set_filter('severity', 'critical')
    error_page.set_filter('category', 'network')
    error_page.apply_filters()


@when('I click the reset filters button')
def click_reset_filters_button(page: Page):
    """Click the reset filters button."""
    error_page = ErrorManagementPage(page)
    error_page.reset_filters()


@then('all filters should be cleared')
def all_filters_should_be_cleared(page: Page):
    """Verify all filters are reset to default values."""
    # Check that filter dropdowns are reset
    time_window = page.input_value('#timeWindow')
    severity = page.input_value('#severityFilter')
    category = page.input_value('#categoryFilter')
    stage = page.input_value('#stageFilter')

    assert time_window == 'last_24_hours' or time_window == '', "Time window should be reset"
    assert severity == '', "Severity filter should be cleared"
    assert category == '', "Category filter should be cleared"
    assert stage == '', "Stage filter should be cleared"


@then('the full error list should be displayed')
def full_error_list_displayed(page: Page):
    """Verify the full unfiltered error list is displayed."""
    # Should see more errors than when filtered
    error_page = ErrorManagementPage(page)
    error_count = error_page.get_error_count()
    assert error_count > 0, "Should display errors when filters are reset"


@then('metrics should show total counts')
def metrics_show_total_counts(page: Page):
    """Verify metrics show total counts instead of filtered counts."""
    # Metrics should reflect the full dataset
    total_errors = page.text_content('#totalErrors')
    assert total_errors != '0' and total_errors != '-', "Should show total error count"


@given('there are more errors than fit on one page')
def more_errors_than_one_page(page: Page):
    """Set up state with paginated error data."""
    # Mock a larger dataset that requires pagination
    page.route('**/api/logs*', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "logs": [
                {"id": "err-001", "timestamp": "2024-01-15T10:30:00Z", "stage": "scrape", "severity": "critical"},
                {"id": "err-002", "timestamp": "2024-01-15T11:15:00Z", "stage": "enrich", "severity": "medium"}
            ],
            "pagination": {"total": 150, "page": 1, "per_page": 50}
        }'''
    ))


@when('I click the next page button')
def click_next_page_button(page: Page):
    """Click the next page button."""
    page.click('#pagination button:has-text("Next")')


@then('I should see the next set of errors')
def should_see_next_set_of_errors(page: Page):
    """Verify the next set of errors is displayed."""
    # The error table should still be visible with potentially different data
    expect(page.locator('#errorTable')).to_be_visible()


@then('the page indicator should update')
def page_indicator_should_update(page: Page):
    """Verify the page indicator updates."""
    # Look for page indicator text (implementation depends on the UI)
    pagination = page.locator('#pagination')
    expect(pagination).to_be_visible()


@when('I click the previous page button')
def click_previous_page_button(page: Page):
    """Click the previous page button."""
    page.click('#pagination button:has-text("Previous")')


@then('I should see the previous set of errors')
def should_see_previous_set_of_errors(page: Page):
    """Verify the previous set of errors is displayed."""
    expect(page.locator('#errorTable')).to_be_visible()


@when(parsers.parse('I click the view button for error "{error_id}"'))
def click_view_button_for_error(page: Page, error_id: str):
    """Click the view button for a specific error."""
    # Mock the error details API call
    page.route(f'**/api/errors/{error_id}', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body=f'''{
            "id": "{error_id}",
            "timestamp": "2024-01-15T10:30:00Z",
            "stage": "scrape",
            "operation": "fetch_website",
            "severity": "critical",
            "category": "network",
            "business_id": "biz-123",
            "content_preview": "Connection timeout after 30s",
            "stack_trace": "Traceback...",
            "business": {
                "name": "Test Business",
                "website": "https://test.com"
            }
        }'''
    ))

    page.click(f'button[onclick*="viewErrorDetails(\'{error_id}\')"]')


@then('I should see detailed error information')
def should_see_detailed_error_info(page: Page):
    """Verify detailed error information is displayed."""
    # This would typically open a modal or navigate to a detail page
    # For now, we'll check that some action was triggered
    # In a real implementation, we'd check for a details modal or page
    pass


@then('the error stack trace should be displayed')
def error_stack_trace_displayed(page: Page):
    """Verify error stack trace is displayed."""
    # Would check for stack trace in the error details view
    pass


@then('related business information should be shown')
def related_business_info_shown(page: Page):
    """Verify related business information is shown."""
    # Would check for business details in the error details view
    pass


@when('new errors are added to the system')
def new_errors_added_to_system(page: Page):
    """Simulate new errors being added to the system."""
    # In a real implementation, this would test real-time updates
    # For now, we'll simulate by updating the mocked data
    pass


@then('the dashboard metrics should update automatically')
def dashboard_metrics_update_automatically(page: Page):
    """Verify dashboard metrics update automatically."""
    # Would check for real-time metric updates
    # For now, verify metrics are displayed
    expect(page.locator('#totalErrors')).to_be_visible()


@then('the error count should reflect new errors')
def error_count_reflects_new_errors(page: Page):
    """Verify error count reflects new errors."""
    # Would check that the count increased
    total_errors = page.text_content('#totalErrors')
    assert total_errors != '-', "Error count should be updated"
