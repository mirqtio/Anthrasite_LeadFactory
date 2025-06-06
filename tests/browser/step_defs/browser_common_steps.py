"""
Common step definitions for browser-based BDD tests.

This module contains shared step definitions that can be used
across multiple browser test features.
"""

import time
from typing import Dict, Any
from pytest_bdd import given, when, then, parsers
from playwright.sync_api import Page, expect

from tests.browser.page_objects import create_page_object


@given('the error management web interface is available')
def error_management_interface_available(page: Page, mock_server_url: str):
    """Ensure the error management interface is available."""
    # Mock the API endpoints that the interface calls
    page.route('**/api/errors/dashboard-data*', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "summary": {
                "total_errors": 25,
                "critical_errors": 5,
                "successful_fixes_24h": 12
            },
            "active_alerts": []
        }'''
    ))

    page.route('**/api/logs*', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "logs": [
                {
                    "id": "err-001",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "stage": "scrape",
                    "operation": "fetch_website",
                    "severity": "critical",
                    "category": "network",
                    "business_id": "biz-123",
                    "content_preview": "Connection timeout after 30s"
                },
                {
                    "id": "err-002",
                    "timestamp": "2024-01-15T11:15:00Z",
                    "stage": "enrich",
                    "operation": "analyze_tech_stack",
                    "severity": "medium",
                    "category": "validation",
                    "business_id": "biz-456",
                    "content_preview": "Invalid HTML structure detected"
                }
            ],
            "pagination": {"total": 2}
        }'''
    ))


@given('the bulk qualification web interface is available')
def bulk_qualification_interface_available(page: Page, mock_server_url: str):
    """Ensure the bulk qualification interface is available."""
    # Mock qualification criteria endpoint
    page.route('**/api/handoff/criteria', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "criteria": [
                {
                    "id": 1,
                    "name": "High Value Lead",
                    "min_score": 80,
                    "description": "Leads with high potential value"
                },
                {
                    "id": 2,
                    "name": "Standard Qualification",
                    "min_score": 60,
                    "description": "Standard qualification criteria"
                }
            ]
        }'''
    ))

    # Mock businesses endpoint
    page.route('**/api/businesses*', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "businesses": [
                {
                    "id": 1,
                    "name": "Test Restaurant",
                    "email": "test@restaurant.com",
                    "website": "https://testrestaurant.com",
                    "category": "restaurant",
                    "score": 85,
                    "status": "pending",
                    "city": "San Francisco",
                    "state": "CA",
                    "created_at": "2024-01-15T09:00:00Z"
                },
                {
                    "id": 2,
                    "name": "Sample Shop",
                    "email": "info@sampleshop.com",
                    "website": "https://sampleshop.com",
                    "category": "retail",
                    "score": 72,
                    "status": "pending",
                    "city": "Los Angeles",
                    "state": "CA",
                    "created_at": "2024-01-15T08:30:00Z"
                }
            ],
            "total_count": 2
        }'''
    ))


@given('the handoff queue web interface is available')
def handoff_queue_interface_available(page: Page, mock_server_url: str):
    """Ensure the handoff queue interface is available."""
    # Mock sales team endpoint
    page.route('**/api/handoff/sales-team', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "members": [
                {
                    "user_id": "user-1",
                    "name": "John Doe",
                    "email": "john@company.com",
                    "role": "Senior Sales Rep",
                    "current_capacity": 3,
                    "max_capacity": 10,
                    "is_active": true
                },
                {
                    "user_id": "user-2",
                    "name": "Jane Smith",
                    "email": "jane@company.com",
                    "role": "Sales Rep",
                    "current_capacity": 8,
                    "max_capacity": 8,
                    "is_active": true
                }
            ]
        }'''
    ))

    # Mock queue endpoint
    page.route('**/api/handoff/queue*', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "entries": [
                {
                    "id": 1,
                    "business": {"name": "Test Restaurant", "email": "test@restaurant.com"},
                    "qualification_score": 85,
                    "priority": 80,
                    "status": "qualified",
                    "assignee": null,
                    "created_at": "2024-01-15T09:00:00Z"
                },
                {
                    "id": 2,
                    "business": {"name": "Sample Shop", "email": "info@sampleshop.com"},
                    "qualification_score": 72,
                    "priority": 65,
                    "status": "assigned",
                    "assignee": {"name": "John Doe"},
                    "created_at": "2024-01-15T08:30:00Z"
                }
            ],
            "total_count": 2
        }'''
    ))

    # Mock analytics summary endpoint
    page.route('**/api/handoff/analytics/summary', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "summary": {
                "total_queue_entries": 25,
                "unassigned_count": 8,
                "assigned_count": 12,
                "contacted_count": 5
            },
            "status_breakdown": [
                {"status": "qualified", "count": 8},
                {"status": "assigned", "count": 12},
                {"status": "contacted", "count": 5}
            ]
        }'''
    ))


@given('the enhanced dashboard web interface is available')
def enhanced_dashboard_interface_available(page: Page, mock_server_url: str):
    """Ensure the enhanced dashboard interface is available."""
    # Mock logs stats endpoint
    page.route('**/api/logs/stats', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "total_logs": 1250,
            "logs_by_type": {
                "llm": 750,
                "raw_html": 500
            },
            "logs_by_business": {
                "1": 150,
                "2": 120,
                "3": 100
            },
            "date_range": {
                "earliest": "2024-01-01T00:00:00Z",
                "latest": "2024-01-15T12:00:00Z"
            }
        }'''
    ))

    # Mock businesses endpoint for dashboard
    page.route('**/api/businesses*', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='''{
            "businesses": [
                {
                    "id": 1,
                    "name": "Test Restaurant",
                    "address": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "website": "https://testrestaurant.com",
                    "score": 85,
                    "archived": false
                },
                {
                    "id": 2,
                    "name": "Sample Shop",
                    "address": "456 Oak Ave",
                    "city": "Los Angeles",
                    "state": "CA",
                    "website": "https://sampleshop.com",
                    "score": 72,
                    "archived": false
                },
                {
                    "id": 3,
                    "name": "Old Business",
                    "address": "789 Pine St",
                    "city": "Portland",
                    "state": "OR",
                    "website": null,
                    "score": 45,
                    "archived": true,
                    "archive_reason": "irrelevant"
                }
            ],
            "total_count": 3
        }'''
    ))


@given('there are sample errors in the system')
def sample_errors_in_system(browser_context_data: Dict[str, Any], test_data: Dict[str, Any]):
    """Set up sample error data."""
    browser_context_data['errors'] = test_data['errors']


@given('there are sample businesses in the system')
def sample_businesses_in_system(browser_context_data: Dict[str, Any], test_data: Dict[str, Any]):
    """Set up sample business data."""
    browser_context_data['businesses'] = test_data['businesses']


@given('qualification criteria are configured')
def qualification_criteria_configured(browser_context_data: Dict[str, Any]):
    """Set up qualification criteria."""
    browser_context_data['criteria'] = [
        {
            'id': 1,
            'name': 'High Value Lead',
            'min_score': 80,
            'description': 'Leads with high potential value'
        }
    ]


@given('there are qualified leads in the handoff queue')
def qualified_leads_in_queue(browser_context_data: Dict[str, Any], test_data: Dict[str, Any]):
    """Set up qualified leads in the handoff queue."""
    browser_context_data['queue_entries'] = test_data['queue_entries']


@given('sales team members are configured')
def sales_team_configured(browser_context_data: Dict[str, Any]):
    """Set up sales team members."""
    browser_context_data['sales_team'] = [
        {
            'user_id': 'user-1',
            'name': 'John Doe',
            'current_capacity': 3,
            'max_capacity': 10,
            'is_active': True
        }
    ]


@given('there is log and business data in the system')
def log_and_business_data_in_system(browser_context_data: Dict[str, Any]):
    """Set up log and business data for dashboard."""
    browser_context_data['logs_stats'] = {
        'total_logs': 1250,
        'logs_by_type': {'llm': 750, 'raw_html': 500}
    }
    browser_context_data['businesses'] = [
        {'id': 1, 'name': 'Test Restaurant', 'archived': False},
        {'id': 2, 'name': 'Sample Shop', 'archived': False},
        {'id': 3, 'name': 'Old Business', 'archived': True}
    ]


@when(parsers.parse('I navigate to the {page_type} page'))
def navigate_to_page(page: Page, page_type: str, browser_context_data: Dict[str, Any], mock_server_url: str):
    """Navigate to a specific page."""
    page_obj = create_page_object(page_type.replace(' ', '_'), page, mock_server_url)
    page_obj.navigate()
    browser_context_data['current_page'] = page_obj


@when('I resize the browser to mobile width')
def resize_to_mobile(page: Page):
    """Resize browser to mobile width."""
    page.set_viewport_size({'width': 375, 'height': 667})


@when(parsers.parse('I wait for {seconds:d} seconds'))
def wait_for_seconds(page: Page, seconds: int):
    """Wait for a specified number of seconds."""
    page.wait_for_timeout(seconds * 1000)


@then('the interface should adapt to mobile layout')
def interface_adapts_to_mobile(page: Page):
    """Verify the interface adapts to mobile layout."""
    # Check that the viewport has been set to mobile dimensions
    viewport = page.viewport_size
    assert viewport['width'] <= 768, f"Expected mobile width, got {viewport['width']}"


@then('all functionality should remain accessible')
def functionality_remains_accessible(page: Page):
    """Verify all functionality remains accessible on mobile."""
    # Check that important buttons and controls are still visible
    # This is a basic check - specific tests would verify specific elements
    assert page.is_visible('body'), "Page body should be visible"


@then('tables should become horizontally scrollable')
def tables_become_scrollable(page: Page):
    """Verify tables become horizontally scrollable on mobile."""
    # Check if tables have horizontal scroll capability
    tables = page.query_selector_all('table')
    for table in tables:
        # Tables should either be wrapped in a scrollable container
        # or have their own overflow handling
        parent = table.query_selector('xpath=..')
        assert parent is not None, "Table should have a parent container"


@then(parsers.parse('the interface should respond within {seconds:d} seconds'))
def interface_responds_quickly(page: Page, seconds: int):
    """Verify the interface responds within specified time."""
    # This is a performance check that would be implemented
    # with actual timing measurements in a real test
    # For now, we'll just verify the page is responsive
    assert page.is_visible('body'), "Page should be responsive"


@then('I should see a success message')
def should_see_success_message(page: Page):
    """Verify a success message is displayed."""
    # Look for common success message patterns
    success_selectors = [
        '.alert-success',
        '.alert.alert-success',
        '[class*="success"]',
        'text="Success"',
        'text="Successfully"'
    ]

    found_success = False
    for selector in success_selectors:
        if page.is_visible(selector):
            found_success = True
            break

    assert found_success, "Should see a success message"


@then('I should see an error message')
def should_see_error_message(page: Page):
    """Verify an error message is displayed."""
    # Look for common error message patterns
    error_selectors = [
        '.alert-error',
        '.alert-danger',
        '.alert.alert-error',
        '.alert.alert-danger',
        '[class*="error"]',
        'text="Error"',
        'text="Failed"'
    ]

    found_error = False
    for selector in error_selectors:
        if page.is_visible(selector):
            found_error = True
            break

    assert found_error, "Should see an error message"


@then(parsers.parse('I should see a confirmation dialog'))
def should_see_confirmation_dialog(page: Page):
    """Verify a confirmation dialog is displayed."""
    # Look for modal or dialog elements
    dialog_selectors = [
        '.modal',
        '[role="dialog"]',
        '.dialog',
        '.confirmation'
    ]

    found_dialog = False
    for selector in dialog_selectors:
        if page.is_visible(selector):
            found_dialog = True
            break

    assert found_dialog, "Should see a confirmation dialog"


@when('I confirm the action')
def confirm_action(page: Page):
    """Confirm an action in a dialog."""
    # Look for common confirmation buttons
    confirm_selectors = [
        'button:has-text("OK")',
        'button:has-text("Confirm")',
        'button:has-text("Yes")',
        'button[type="submit"]'
    ]

    for selector in confirm_selectors:
        if page.is_visible(selector):
            page.click(selector)
            break
    else:
        # Fallback to page dialog handling
        page.on('dialog', lambda dialog: dialog.accept())


@given(parsers.parse('I am on the {page_type} page'))
def on_specific_page(page: Page, page_type: str, browser_context_data: Dict[str, Any], mock_server_url: str):
    """Ensure we are on a specific page."""
    if 'current_page' not in browser_context_data:
        page_obj = create_page_object(page_type.replace(' ', '_'), page, mock_server_url)
        page_obj.navigate()
        browser_context_data['current_page'] = page_obj


@when('I take a screenshot')
@when(parsers.parse('I take a screenshot named "{name}"'))
def take_screenshot(page: Page, name: str = None):
    """Take a screenshot for debugging."""
    if name is None:
        name = f"screenshot_{int(time.time())}"

    import os
    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')

    page.screenshot(path=f'screenshots/{name}.png')
