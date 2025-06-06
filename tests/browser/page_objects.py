"""
Page Object Models for UI components.

This module provides page object models that encapsulate the structure
and interactions of the web interfaces.
"""

from typing import List, Dict, Any, Optional
from playwright.sync_api import Page, Locator


class BasePage:
    """Base page object with common functionality."""

    def __init__(self, page: Page):
        self.page = page

    def navigate_to(self, url: str):
        """Navigate to a URL."""
        self.page.goto(url)
        self.page.wait_for_load_state('networkidle')

    def wait_for_element(self, selector: str, timeout: int = 5000):
        """Wait for an element to be visible."""
        return self.page.wait_for_selector(selector, timeout=timeout)

    def click_element(self, selector: str):
        """Click an element with waiting."""
        self.page.wait_for_selector(selector)
        self.page.click(selector)

    def fill_input(self, selector: str, value: str):
        """Fill an input field."""
        self.page.wait_for_selector(selector)
        self.page.fill(selector, value)

    def select_option(self, selector: str, value: str):
        """Select an option from a dropdown."""
        self.page.wait_for_selector(selector)
        self.page.select_option(selector, value)

    def get_text(self, selector: str) -> str:
        """Get text content of an element."""
        return self.page.text_content(selector)

    def is_visible(self, selector: str) -> bool:
        """Check if an element is visible."""
        try:
            element = self.page.query_selector(selector)
            return element.is_visible() if element else False
        except:
            return False

    def take_screenshot(self, name: str):
        """Take a screenshot."""
        self.page.screenshot(path=f'screenshots/{name}.png')


class ErrorManagementPage(BasePage):
    """Page object for Error Management Dashboard."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page)
        self.base_url = base_url
        self.url = f"{base_url}/error_management.html"

        # Selectors
        self.metrics = {
            'total_errors': '#totalErrors',
            'critical_errors': '#criticalErrors',
            'fixed_errors': '#fixedErrors'
        }

        self.filters = {
            'time_window': '#timeWindow',
            'severity': '#severityFilter',
            'category': '#categoryFilter',
            'stage': '#stageFilter'
        }

        self.buttons = {
            'apply_filters': 'button:has-text("Apply Filters")',
            'reset_filters': 'button:has-text("Reset")',
            'bulk_fix': 'button:has-text("Bulk Fix")',
            'bulk_dismiss': 'button:has-text("Bulk Dismiss")',
            'bulk_categorize': 'button:has-text("Bulk Categorize")'
        }

        self.table = {
            'error_table': '#errorTable',
            'error_rows': '#errorTableBody tr',
            'select_all': '#selectAll',
            'bulk_actions': '#bulkActions'
        }

        self.modals = {
            'bulk_dismiss': '#bulkDismissModal',
            'bulk_fix': '#bulkFixModal',
            'bulk_categorize': '#bulkCategorizeModal'
        }

    def navigate(self):
        """Navigate to the error management page."""
        self.navigate_to(self.url)

    def get_metric_value(self, metric: str) -> str:
        """Get the value of a metric."""
        return self.get_text(self.metrics[metric])

    def set_filter(self, filter_name: str, value: str):
        """Set a filter value."""
        self.select_option(self.filters[filter_name], value)

    def apply_filters(self):
        """Apply the current filters."""
        self.click_element(self.buttons['apply_filters'])
        self.page.wait_for_timeout(1000)  # Wait for data to load

    def reset_filters(self):
        """Reset all filters."""
        self.click_element(self.buttons['reset_filters'])
        self.page.wait_for_timeout(1000)

    def select_all_errors(self):
        """Select all visible errors."""
        self.click_element(self.table['select_all'])

    def select_error(self, error_id: str):
        """Select a specific error by ID."""
        checkbox_selector = f'input[onchange*="{error_id}"]'
        self.click_element(checkbox_selector)

    def get_selected_count(self) -> str:
        """Get the number of selected errors."""
        return self.get_text('#selectedCount')

    def open_bulk_dismiss_modal(self):
        """Open the bulk dismiss modal."""
        self.click_element(self.buttons['bulk_dismiss'])
        self.wait_for_element(self.modals['bulk_dismiss'])

    def perform_bulk_dismiss(self, reason: str, comment: str = ""):
        """Perform bulk dismiss operation."""
        self.open_bulk_dismiss_modal()
        self.select_option('#dismissReason', reason)
        if comment:
            self.fill_input('#dismissComment', comment)
        self.click_element('button[type="submit"]:has-text("Dismiss Selected Errors")')

    def get_error_count(self) -> int:
        """Get the number of visible errors in the table."""
        rows = self.page.query_selector_all(self.table['error_rows'])
        return len(rows)

    def is_bulk_actions_visible(self) -> bool:
        """Check if bulk actions section is visible."""
        return self.is_visible(self.table['bulk_actions'] + '.visible')


class BulkQualificationPage(BasePage):
    """Page object for Bulk Lead Qualification."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page)
        self.base_url = base_url
        self.url = f"{base_url}/bulk_qualification.html"

        # Selectors
        self.controls = {
            'qualification_criteria': '#qualificationCriteria',
            'business_filter': '#businessFilter',
            'min_score': '#minScore',
            'sort_by': '#sortBy'
        }

        self.buttons = {
            'qualify_selected': '#qualifySelectedBtn',
            'select_all': '#selectAllBtn',
            'clear_selection': '#clearSelectionBtn',
            'refresh': '#refreshBtn'
        }

        self.search = {
            'search_input': '#searchInput',
            'category_filter': '#categoryFilter'
        }

        self.table = {
            'businesses_table': '#businessesTable',
            'business_rows': '#businessesTableBody tr',
            'select_all_checkbox': '#selectAllCheckbox'
        }

        self.modal = '#qualificationModal'

    def navigate(self):
        """Navigate to the bulk qualification page."""
        self.navigate_to(self.url)

    def set_qualification_criteria(self, criteria_id: str):
        """Set the qualification criteria."""
        self.select_option(self.controls['qualification_criteria'], criteria_id)

    def set_business_filter(self, filter_value: str):
        """Set the business filter."""
        self.select_option(self.controls['business_filter'], filter_value)

    def set_minimum_score(self, score: str):
        """Set the minimum score filter."""
        self.fill_input(self.controls['min_score'], score)

    def search_businesses(self, search_term: str):
        """Search for businesses."""
        self.fill_input(self.search['search_input'], search_term)
        self.page.wait_for_timeout(1000)  # Wait for debounced search

    def select_all_businesses(self):
        """Select all visible businesses."""
        self.click_element(self.table['select_all_checkbox'])

    def select_business(self, business_id: int):
        """Select a specific business."""
        checkbox_selector = f'input[onchange*="toggleBusinessSelection({business_id}"]'
        self.click_element(checkbox_selector)

    def get_selected_count(self) -> str:
        """Get the selected count text."""
        return self.get_text('#selectedCount')

    def qualify_selected_businesses(self):
        """Start the qualification process for selected businesses."""
        self.click_element(self.buttons['qualify_selected'])
        self.wait_for_element(self.modal)

    def get_business_count(self) -> int:
        """Get the number of visible businesses."""
        rows = self.page.query_selector_all(self.table['business_rows'])
        return len([row for row in rows if row.query_selector('td') is not None])

    def is_qualify_button_enabled(self) -> bool:
        """Check if the qualify button is enabled."""
        button = self.page.query_selector(self.buttons['qualify_selected'])
        return not button.get_attribute('disabled')


class HandoffQueuePage(BasePage):
    """Page object for Handoff Queue Dashboard."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page)
        self.base_url = base_url
        self.url = f"{base_url}/handoff_queue.html"

        # Selectors
        self.stats = {
            'total_queue': '#totalQueueStat',
            'unassigned': '#unassignedStat',
            'assigned': '#assignedStat',
            'contacted': '#contactedStat'
        }

        self.filters = {
            'status_filter': '#statusFilter',
            'assignee_filter': '#assigneeFilter',
            'min_priority': '#minPriority',
            'sales_member': '#salesMemberSelect'
        }

        self.buttons = {
            'assign_selected': '#assignSelectedBtn',
            'select_all': '#selectAllBtn',
            'clear_selection': '#clearSelectionBtn',
            'refresh': '#refreshBtn'
        }

        self.table = {
            'queue_table': '#queueTable',
            'queue_rows': '#queueTableBody tr',
            'select_all_checkbox': '#selectAllCheckbox'
        }

        self.modal = '#assignmentModal'

    def navigate(self):
        """Navigate to the handoff queue page."""
        self.navigate_to(self.url)

    def get_stat_value(self, stat: str) -> str:
        """Get a statistic value."""
        return self.get_text(self.stats[stat])

    def set_status_filter(self, status: str):
        """Set the status filter."""
        self.select_option(self.filters['status_filter'], status)

    def set_assignee_filter(self, assignee: str):
        """Set the assignee filter."""
        self.select_option(self.filters['assignee_filter'], assignee)

    def set_minimum_priority(self, priority: str):
        """Set the minimum priority filter."""
        self.fill_input(self.filters['min_priority'], priority)

    def select_sales_member(self, member_id: str):
        """Select a sales member for assignment."""
        self.select_option(self.filters['sales_member'], member_id)

    def select_queue_entry(self, entry_id: int):
        """Select a queue entry."""
        checkbox_selector = f'input[onchange*="toggleEntrySelection({entry_id}"]'
        self.click_element(checkbox_selector)

    def assign_selected_entries(self):
        """Assign selected entries to the chosen sales member."""
        self.click_element(self.buttons['assign_selected'])
        self.wait_for_element(self.modal)

    def get_queue_entry_count(self) -> int:
        """Get the number of visible queue entries."""
        rows = self.page.query_selector_all(self.table['queue_rows'])
        return len([row for row in rows if row.query_selector('td') is not None])

    def view_entry_details(self, entry_id: int):
        """View details of a queue entry."""
        button_selector = f'button[onclick*="viewEntryDetails({entry_id})"]'
        self.click_element(button_selector)


class EnhancedDashboardPage(BasePage):
    """Page object for Enhanced Cost Dashboard."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page)
        self.base_url = base_url
        self.url = f"{base_url}/dashboard.html"

        # Selectors
        self.filters = {
            'time_range': '#time-range',
            'business_filter': '#business-filter',
            'start_date': '#start-date',
            'end_date': '#end-date'
        }

        self.stats = {
            'total_logs': '#total-logs',
            'total_businesses': '#total-businesses',
            'llm_logs': '#llm-logs',
            'html_logs': '#html-logs'
        }

        self.buttons = {
            'refresh': '#refresh-button',
            'bulk_reject': '#bulk-reject-btn',
            'prev_page': '#prev-page',
            'next_page': '#next-page'
        }

        self.business_management = {
            'search': '#business-search',
            'archived_filter': '#archived-filter',
            'select_all': '#select-all-businesses',
            'business_table': '#business-list-table'
        }

    def navigate(self):
        """Navigate to the enhanced dashboard."""
        self.navigate_to(self.url)

    def set_time_range(self, range_value: str):
        """Set the time range filter."""
        self.select_option(self.filters['time_range'], range_value)

    def set_business_filter(self, business_id: str):
        """Set the business filter."""
        self.select_option(self.filters['business_filter'], business_id)

    def refresh_data(self):
        """Refresh the dashboard data."""
        self.click_element(self.buttons['refresh'])
        self.page.wait_for_timeout(2000)  # Wait for data to load

    def get_stat_value(self, stat: str) -> str:
        """Get a statistic value."""
        return self.get_text(self.stats[stat])

    def search_businesses(self, search_term: str):
        """Search for businesses in the management section."""
        self.fill_input(self.business_management['search'], search_term)
        self.page.wait_for_timeout(1000)  # Wait for debounced search

    def set_archived_filter(self, filter_value: str):
        """Set the archived businesses filter."""
        self.select_option(self.business_management['archived_filter'], filter_value)

    def select_business_for_action(self, business_id: int):
        """Select a business for bulk actions."""
        checkbox_selector = f'input.business-checkbox[value="{business_id}"]'
        self.click_element(checkbox_selector)

    def bulk_reject_businesses(self):
        """Perform bulk reject operation."""
        self.click_element(self.buttons['bulk_reject'])

    def get_business_count_text(self) -> str:
        """Get the business count text."""
        return self.get_text('#business-count')

    def is_chart_visible(self, chart_id: str) -> bool:
        """Check if a chart is visible and rendered."""
        return self.is_visible(f'#{chart_id}')


# Factory function for creating page objects
def create_page_object(page_type: str, page: Page, base_url: str = "http://localhost:8080"):
    """Factory function to create page objects."""
    page_objects = {
        'error_management': ErrorManagementPage,
        'bulk_qualification': BulkQualificationPage,
        'handoff_queue': HandoffQueuePage,
        'enhanced_dashboard': EnhancedDashboardPage
    }

    if page_type not in page_objects:
        raise ValueError(f"Unknown page type: {page_type}")

    return page_objects[page_type](page, base_url)
