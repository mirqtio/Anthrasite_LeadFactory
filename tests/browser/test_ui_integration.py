"""
Integration tests for browser-based UI components.

This module contains pytest tests that use the BDD scenarios
and demonstrate the full browser testing capabilities.
"""

import pytest
from pytest_bdd import scenarios, given, when, then
from playwright.sync_api import Page, expect

from tests.browser.page_objects import (
    ErrorManagementPage,
    BulkQualificationPage,
    HandoffQueuePage,
    EnhancedDashboardPage
)

# Load all BDD scenarios
scenarios('features/error_management_ui.feature')
scenarios('features/bulk_qualification_ui.feature')
scenarios('features/handoff_queue_ui.feature')
scenarios('features/enhanced_dashboard_ui.feature')


class TestErrorManagementUI:
    """Test class for Error Management UI."""

    def test_error_management_page_loads(self, page: Page, mock_server_url: str):
        """Test that the error management page loads correctly."""
        error_page = ErrorManagementPage(page, mock_server_url)
        error_page.navigate()

        # Verify page elements are present
        expect(page.locator('h1')).to_contain_text('Error Management Dashboard')
        expect(page.locator('#totalErrors')).to_be_visible()
        expect(page.locator('#errorTable')).to_be_visible()

    def test_error_filtering_works(self, page: Page, mock_server_url: str):
        """Test that error filtering functionality works."""
        error_page = ErrorManagementPage(page, mock_server_url)
        error_page.navigate()

        # Test severity filter
        error_page.set_filter('severity', 'critical')
        error_page.apply_filters()

        # Verify table still displays
        expect(page.locator('#errorTable')).to_be_visible()

    def test_bulk_operations_modal_opens(self, page: Page, mock_server_url: str):
        """Test that bulk operations modals open correctly."""
        error_page = ErrorManagementPage(page, mock_server_url)
        error_page.navigate()

        # Select an error first
        error_page.select_all_errors()

        # Test bulk dismiss modal
        error_page.open_bulk_dismiss_modal()
        expect(page.locator('#bulkDismissModal')).to_be_visible()


class TestBulkQualificationUI:
    """Test class for Bulk Qualification UI."""

    def test_qualification_page_loads(self, page: Page, mock_server_url: str):
        """Test that the bulk qualification page loads correctly."""
        qualification_page = BulkQualificationPage(page, mock_server_url)
        qualification_page.navigate()

        # Verify page elements are present
        expect(page.locator('h1')).to_contain_text('Bulk Lead Qualification')
        expect(page.locator('#qualificationCriteria')).to_be_visible()
        expect(page.locator('#businessesTable')).to_be_visible()

    def test_business_selection_works(self, page: Page, mock_server_url: str):
        """Test that business selection functionality works."""
        qualification_page = BulkQualificationPage(page, mock_server_url)
        qualification_page.navigate()

        # Wait for data to load
        page.wait_for_timeout(1000)

        # Select all businesses
        qualification_page.select_all_businesses()

        # Verify selection count updates
        selected_count = qualification_page.get_selected_count()
        assert 'selected' in selected_count

    def test_qualification_criteria_loading(self, page: Page, mock_server_url: str):
        """Test that qualification criteria are loaded correctly."""
        qualification_page = BulkQualificationPage(page, mock_server_url)
        qualification_page.navigate()

        # Wait for criteria to load
        page.wait_for_timeout(1000)

        # Verify criteria dropdown has options
        options = page.query_selector_all('#qualificationCriteria option')
        assert len(options) > 1, "Should have qualification criteria loaded"


class TestHandoffQueueUI:
    """Test class for Handoff Queue UI."""

    def test_handoff_queue_loads(self, page: Page, mock_server_url: str):
        """Test that the handoff queue page loads correctly."""
        queue_page = HandoffQueuePage(page, mock_server_url)
        queue_page.navigate()

        # Verify page elements are present
        expect(page.locator('h1')).to_contain_text('Handoff Queue Dashboard')
        expect(page.locator('#totalQueueStat')).to_be_visible()
        expect(page.locator('#queueTable')).to_be_visible()

    def test_queue_statistics_display(self, page: Page, mock_server_url: str):
        """Test that queue statistics are displayed correctly."""
        queue_page = HandoffQueuePage(page, mock_server_url)
        queue_page.navigate()

        # Wait for stats to load
        page.wait_for_timeout(1000)

        # Verify stats show actual numbers
        total_queue = queue_page.get_stat_value('total_queue')
        assert total_queue != '-', "Total queue stat should show actual number"

    def test_sales_team_loading(self, page: Page, mock_server_url: str):
        """Test that sales team members are loaded correctly."""
        queue_page = HandoffQueuePage(page, mock_server_url)
        queue_page.navigate()

        # Wait for sales team to load
        page.wait_for_timeout(1000)

        # Verify sales member dropdown has options
        options = page.query_selector_all('#salesMemberSelect option')
        assert len(options) > 1, "Should have sales team members loaded"


class TestEnhancedDashboardUI:
    """Test class for Enhanced Dashboard UI."""

    def test_dashboard_loads(self, page: Page, mock_server_url: str):
        """Test that the enhanced dashboard loads correctly."""
        dashboard_page = EnhancedDashboardPage(page, mock_server_url)
        dashboard_page.navigate()

        # Verify page elements are present
        expect(page.locator('h1')).to_contain_text('Analytics Dashboard')
        expect(page.locator('#total-logs')).to_be_visible()
        expect(page.locator('#business-list-table')).to_be_visible()

    def test_statistics_loading(self, page: Page, mock_server_url: str):
        """Test that statistics are loaded correctly."""
        dashboard_page = EnhancedDashboardPage(page, mock_server_url)
        dashboard_page.navigate()

        # Wait for stats to load
        page.wait_for_timeout(2000)

        # Verify stats show actual numbers
        total_logs = dashboard_page.get_stat_value('total_logs')
        assert total_logs != '-', "Total logs stat should show actual number"

    def test_business_management_functionality(self, page: Page, mock_server_url: str):
        """Test that business management functionality works."""
        dashboard_page = EnhancedDashboardPage(page, mock_server_url)
        dashboard_page.navigate()

        # Wait for businesses to load
        page.wait_for_timeout(2000)

        # Test search functionality
        dashboard_page.search_businesses('Test')

        # Verify table is still visible
        expect(page.locator('#business-list-table')).to_be_visible()


class TestCrossComponentIntegration:
    """Test class for cross-component integration."""

    def test_navigation_between_components(self, page: Page, mock_server_url: str):
        """Test navigation between different UI components."""
        # Start with bulk qualification
        qualification_page = BulkQualificationPage(page, mock_server_url)
        qualification_page.navigate()
        expect(page.locator('h1')).to_contain_text('Bulk Lead Qualification')

        # Navigate to handoff queue via link
        page.click('a:has-text("View Handoff Queue")')
        expect(page.locator('h1')).to_contain_text('Handoff Queue Dashboard')

        # Navigate back to bulk qualification via link
        page.click('a:has-text("Bulk Qualification")')
        expect(page.locator('h1')).to_contain_text('Bulk Lead Qualification')

    def test_responsive_design_across_components(self, page: Page, mock_server_url: str):
        """Test responsive design across all components."""
        components = [
            (ErrorManagementPage, 'Error Management Dashboard'),
            (BulkQualificationPage, 'Bulk Lead Qualification'),
            (HandoffQueuePage, 'Handoff Queue Dashboard'),
            (EnhancedDashboardPage, 'Analytics Dashboard')
        ]

        for page_class, expected_title in components:
            # Test desktop view
            page.set_viewport_size({'width': 1280, 'height': 720})
            component_page = page_class(page, mock_server_url)
            component_page.navigate()
            expect(page.locator('h1')).to_contain_text(expected_title)

            # Test mobile view
            page.set_viewport_size({'width': 375, 'height': 667})
            expect(page.locator('h1')).to_be_visible()

            # Verify mobile adaptations
            assert page.viewport_size['width'] == 375, "Should be in mobile viewport"

    def test_api_error_handling(self, page: Page, mock_server_url: str):
        """Test how components handle API errors."""
        # Mock API to return errors
        page.route('**/api/**', lambda route: route.fulfill(
            status=500,
            content_type='application/json',
            body='{"error": "Internal server error"}'
        ))

        # Test error management page
        error_page = ErrorManagementPage(page, mock_server_url)
        error_page.navigate()

        # Page should still load even with API errors
        expect(page.locator('h1')).to_contain_text('Error Management Dashboard')

        # Error metrics might show defaults or error states
        expect(page.locator('#totalErrors')).to_be_visible()


class TestPerformanceAndAccessibility:
    """Test class for performance and accessibility."""

    def test_page_load_performance(self, page: Page, mock_server_url: str):
        """Test that pages load within acceptable time limits."""
        import time

        components = [
            ErrorManagementPage,
            BulkQualificationPage,
            HandoffQueuePage,
            EnhancedDashboardPage
        ]

        for page_class in components:
            start_time = time.time()
            component_page = page_class(page, mock_server_url)
            component_page.navigate()

            # Wait for page to be fully loaded
            page.wait_for_load_state('networkidle')
            load_time = time.time() - start_time

            # Assert reasonable load time (adjust as needed)
            assert load_time < 10, f"{page_class.__name__} took {load_time:.2f}s to load"

    def test_keyboard_navigation(self, page: Page, mock_server_url: str):
        """Test keyboard navigation accessibility."""
        error_page = ErrorManagementPage(page, mock_server_url)
        error_page.navigate()

        # Test tab navigation
        page.keyboard.press('Tab')
        focused_element = page.evaluate('document.activeElement.tagName')

        # Should focus on a focusable element
        assert focused_element in ['INPUT', 'BUTTON', 'SELECT', 'A'], \
            f"Should focus on interactive element, got {focused_element}"

    def test_basic_accessibility_compliance(self, page: Page, mock_server_url: str):
        """Test basic accessibility compliance."""
        error_page = ErrorManagementPage(page, mock_server_url)
        error_page.navigate()

        # Check for basic accessibility features
        # Page should have a title
        title = page.title()
        assert len(title) > 0, "Page should have a title"

        # Should have proper heading structure
        h1_elements = page.query_selector_all('h1')
        assert len(h1_elements) > 0, "Page should have at least one h1 element"

        # Form inputs should have labels
        inputs = page.query_selector_all('input[type="text"], input[type="number"], select')
        for input_element in inputs:
            # Check if input has label or aria-label
            input_id = input_element.get_attribute('id')
            aria_label = input_element.get_attribute('aria-label')

            if input_id:
                label = page.query_selector(f'label[for="{input_id}"]')
                assert label or aria_label, f"Input {input_id} should have a label or aria-label"


# Pytest hooks for better test reporting
def pytest_configure(config):
    """Configure pytest for browser tests."""
    config.addinivalue_line(
        "markers", "browser: mark test as browser-based UI test"
    )


def pytest_collection_modifyitems(config, items):
    """Add browser marker to all tests in this module."""
    for item in items:
        item.add_marker(pytest.mark.browser)
