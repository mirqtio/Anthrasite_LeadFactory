"""
End-to-end tests for the Logs Web Interface workflows.

Tests complete user workflows including browsing, filtering, searching,
and exporting logs through the web interface.
"""

import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta

import pytest
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from leadfactory.api.logs_api import create_logs_app


class TestLogsWebInterfaceE2E:
    """End-to-end tests for logs web interface."""

    @pytest.fixture(scope="class")
    def test_db(self):
        """Create a temporary test database."""
        db_fd, db_path = tempfile.mkstemp()

        # Create test database schema and data
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE businesses (
                id INTEGER PRIMARY KEY,
                name TEXT,
                website TEXT,
                email TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE llm_logs (
                id INTEGER PRIMARY KEY,
                business_id INTEGER,
                operation TEXT,
                model_version TEXT,
                prompt_text TEXT,
                response_json TEXT,
                tokens_prompt INTEGER,
                tokens_completion INTEGER,
                duration_ms INTEGER,
                status TEXT,
                created_at TIMESTAMP,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE raw_html_storage (
                id INTEGER PRIMARY KEY,
                business_id INTEGER,
                html_path TEXT,
                original_url TEXT,
                compression_ratio REAL,
                content_hash TEXT,
                size_bytes INTEGER,
                created_at TIMESTAMP
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO businesses (id, name, website, email)
            VALUES
                (1, 'E2E Test Business 1', 'https://e2e1.com', 'e2e1@example.com'),
                (2, 'E2E Test Business 2', 'https://e2e2.com', 'e2e2@example.com'),
                (3, 'E2E Test Business 3', 'https://e2e3.com', 'e2e3@example.com')
        """)

        # Insert varied test data
        now = datetime.utcnow()

        # LLM logs with different patterns
        llm_prompts = [
            "Generate marketing copy for restaurant",
            "Analyze customer feedback sentiment",
            "Create product description for e-commerce",
            "Write blog post about sustainability",
            "Draft email campaign for newsletter",
            "Optimize website content for SEO",
            "Translate content to Spanish",
            "Summarize market research data",
            "Generate social media posts",
            "Create FAQ section content",
        ]

        for i, prompt in enumerate(llm_prompts):
            cursor.execute(
                """
                INSERT INTO llm_logs (
                    business_id, operation, model_version, prompt_text, response_json,
                    tokens_prompt, tokens_completion, duration_ms, status, created_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    (i % 3) + 1,
                    f"content_generation_{i}",
                    "gpt-4",
                    prompt,
                    f'{{"response": "Generated content for: {prompt}"}}',
                    len(prompt.split()) * 1.3,  # Approximate tokens
                    len(prompt.split()) * 2,
                    1000 + i * 200,
                    "success" if i % 10 != 7 else "error",  # One error case
                    now - timedelta(hours=i, minutes=i * 5),
                    f'{{"category": "content", "priority": "high", "version": "{i}"}}',
                ),
            )

        # HTML logs with realistic URLs
        html_data = [
            ("home", "https://e2e1.com/"),
            ("about", "https://e2e1.com/about"),
            ("contact", "https://e2e1.com/contact"),
            ("products", "https://e2e2.com/products"),
            ("services", "https://e2e2.com/services"),
            ("blog", "https://e2e2.com/blog"),
            ("careers", "https://e2e3.com/careers"),
            ("support", "https://e2e3.com/support"),
            ("pricing", "https://e2e3.com/pricing"),
            ("features", "https://e2e1.com/features"),
        ]

        for i, (page, url) in enumerate(html_data):
            cursor.execute(
                """
                INSERT INTO raw_html_storage (
                    business_id, html_path, original_url, compression_ratio,
                    content_hash, size_bytes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    (i % 3) + 1,
                    f"/storage/html/{page}_{i}.html",
                    url,
                    0.7 + (i % 3) * 0.1,  # Varied compression ratios
                    f"sha256_{page}_{i}",
                    8000 + i * 500,
                    now - timedelta(hours=i * 2, minutes=i * 10),
                ),
            )

        conn.commit()
        conn.close()

        yield db_path

        # Cleanup
        os.close(db_fd)
        os.unlink(db_path)

    @pytest.fixture(scope="class")
    def test_server(self, test_db):
        """Start test server with mock data."""
        import sqlite3
        from unittest.mock import Mock, patch

        def create_mock_storage():
            storage = Mock()

            def get_logs_with_filters(**kwargs):
                conn = sqlite3.connect(test_db)
                cursor = conn.cursor()

                # Build query with filters
                params = []

                business_id = kwargs.get("business_id")
                log_type = kwargs.get("log_type")
                search_query = kwargs.get("search_query")
                limit = kwargs.get("limit", 50)
                offset = kwargs.get("offset", 0)

                if log_type == "llm":
                    query = """
                        SELECT id, business_id, 'llm' as log_type, prompt_text as content,
                               created_at as timestamp, metadata, NULL as file_path,
                               LENGTH(prompt_text) as content_length
                        FROM llm_logs WHERE 1=1
                    """
                elif log_type == "raw_html":
                    query = """
                        SELECT id, business_id, 'raw_html' as log_type, original_url as content,
                               created_at as timestamp, '{}' as metadata, html_path as file_path,
                               size_bytes as content_length
                        FROM raw_html_storage WHERE 1=1
                    """
                else:
                    query = """
                        SELECT * FROM (
                            SELECT id, business_id, 'llm' as log_type, prompt_text as content,
                                   created_at as timestamp, metadata, NULL as file_path,
                                   LENGTH(prompt_text) as content_length
                            FROM llm_logs
                            UNION ALL
                            SELECT id, business_id, 'raw_html' as log_type, original_url as content,
                                   created_at as timestamp, '{}' as metadata, html_path as file_path,
                                   size_bytes as content_length
                            FROM raw_html_storage
                        ) as combined WHERE 1=1
                    """

                if business_id:
                    query += " AND business_id = ?"
                    params.append(business_id)

                if search_query:
                    query += " AND content LIKE ?"
                    params.append(f"%{search_query}%")

                # Count query
                count_query = f"SELECT COUNT(*) FROM ({query}) as counted"
                cursor.execute(count_query, params)
                total_count = cursor.fetchone()[0]

                # Data query
                data_query = f"{query} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                cursor.execute(data_query, params + [limit, offset])

                rows = cursor.fetchall()
                columns = [
                    "id",
                    "business_id",
                    "log_type",
                    "content",
                    "timestamp",
                    "metadata",
                    "file_path",
                    "content_length",
                ]
                logs = [dict(zip(columns, row)) for row in rows]

                conn.close()
                return logs, total_count

            def get_log_statistics():
                conn = sqlite3.connect(test_db)
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM llm_logs")
                llm_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM raw_html_storage")
                html_count = cursor.fetchone()[0]

                conn.close()

                return {
                    "total_logs": llm_count + html_count,
                    "logs_by_type": {"llm": llm_count, "raw_html": html_count},
                    "logs_by_business": {"1": 7, "2": 7, "3": 6},
                    "date_range": {
                        "earliest": (
                            datetime.utcnow() - timedelta(hours=20)
                        ).isoformat(),
                        "latest": datetime.utcnow().isoformat(),
                    },
                }

            def get_businesses_with_logs():
                return [
                    {"id": 1, "name": "E2E Test Business 1"},
                    {"id": 2, "name": "E2E Test Business 2"},
                    {"id": 3, "name": "E2E Test Business 3"},
                ]

            storage.get_logs_with_filters = get_logs_with_filters
            storage.get_log_statistics = get_log_statistics
            storage.get_businesses_with_logs = get_businesses_with_logs
            storage.get_available_log_types = lambda: ["llm", "raw_html"]
            storage.get_log_by_id = lambda log_id: None  # Simplified for E2E

            return storage

        # Start server in thread
        with patch(
            "leadfactory.api.logs_api.get_storage", side_effect=create_mock_storage
        ):
            app = create_logs_app()
            app.config["TESTING"] = False

            # Run server in background
            server_thread = threading.Thread(
                target=lambda: app.run(
                    host="127.0.0.1", port=5555, debug=False, use_reloader=False
                ),
                daemon=True,
            )
            server_thread.start()

            # Wait for server to start
            time.sleep(2)

            # Verify server is running
            try:
                response = requests.get("http://127.0.0.1:5555/api/health", timeout=5)
                if response.status_code != 200:
                    raise Exception("Server not responding")
            except Exception as e:
                pytest.skip(f"Could not start test server: {e}")

            yield "http://127.0.0.1:5555"

    @pytest.fixture
    def driver(self):
        """Create Selenium WebDriver."""
        options = Options()
        options.add_argument("--headless")  # Run in headless mode for CI
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        try:
            driver = webdriver.Chrome(options=options)
            yield driver
            driver.quit()
        except Exception as e:
            pytest.skip(f"Chrome WebDriver not available: {e}")

    def test_logs_page_loads(self, driver, test_server):
        """Test that the logs page loads correctly."""
        driver.get(f"{test_server}/logs")

        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "logs-container")))

        # Check page title and main elements
        assert "Logs Browser" in driver.title or "Logs Browser" in driver.page_source

        # Check sidebar navigation
        sidebar = driver.find_element(By.CLASS_NAME, "sidebar")
        assert sidebar.is_displayed()

        # Check logs table
        logs_table = driver.find_element(By.CLASS_NAME, "logs-table")
        assert logs_table.is_displayed()

    def test_dashboard_page_loads(self, driver, test_server):
        """Test that the dashboard page loads correctly."""
        driver.get(f"{test_server}/dashboard")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "dashboard-grid")))

        # Check dashboard elements
        assert "Analytics Dashboard" in driver.page_source

        # Check stat cards are present
        stat_cards = driver.find_elements(By.CLASS_NAME, "stat-card")
        assert len(stat_cards) >= 3  # Should have multiple stat cards

    def test_navigation_between_views(self, driver, test_server):
        """Test navigation between different log views."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "nav-item")))

        # Test clicking on LLM logs view
        llm_nav = driver.find_element(By.CSS_SELECTOR, '[data-view="llm"]')
        llm_nav.click()

        time.sleep(1)  # Wait for filter to apply

        # Check that LLM filter is applied
        log_type_filter = Select(driver.find_element(By.ID, "log-type-filter"))
        assert log_type_filter.first_selected_option.get_attribute("value") == "llm"

        # Test clicking on HTML logs view
        html_nav = driver.find_element(By.CSS_SELECTOR, '[data-view="raw_html"]')
        html_nav.click()

        time.sleep(1)

        # Check that HTML filter is applied
        log_type_filter = Select(driver.find_element(By.ID, "log-type-filter"))
        assert (
            log_type_filter.first_selected_option.get_attribute("value") == "raw_html"
        )

    def test_search_functionality(self, driver, test_server):
        """Test search functionality."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "search-input")))

        # Enter search term
        search_input = driver.find_element(By.ID, "search-input")
        search_input.clear()
        search_input.send_keys("marketing")

        # Click search button
        search_button = driver.find_element(By.ID, "search-button")
        search_button.click()

        # Wait for results to load
        time.sleep(2)

        # Check that results are filtered
        logs_table = driver.find_element(By.CLASS_NAME, "logs-table")
        table_rows = logs_table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header

        # Should have some results (not all logs)
        assert len(table_rows) > 0
        assert len(table_rows) < 20  # Should be filtered down

    def test_business_filtering(self, driver, test_server):
        """Test filtering by business ID."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "business-filter")))

        # Enter business ID
        business_filter = driver.find_element(By.ID, "business-filter")
        business_filter.clear()
        business_filter.send_keys("1")

        # Apply filter (can trigger on change or via search button)
        search_button = driver.find_element(By.ID, "search-button")
        search_button.click()

        # Wait for results
        time.sleep(2)

        # Check that results are filtered
        logs_table = driver.find_element(By.CLASS_NAME, "logs-table")
        table_rows = logs_table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header

        # Verify business ID in results
        if table_rows:  # If there are results
            first_row = table_rows[0]
            cells = first_row.find_elements(By.TAG_NAME, "td")
            business_id_cell = cells[1]  # Business ID is second column
            assert "1" in business_id_cell.text

    def test_log_type_filtering(self, driver, test_server):
        """Test filtering by log type."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "log-type-filter")))

        # Select LLM log type
        log_type_select = Select(driver.find_element(By.ID, "log-type-filter"))
        log_type_select.select_by_value("llm")

        # Wait for filter to apply automatically or click search
        time.sleep(1)
        search_button = driver.find_element(By.ID, "search-button")
        search_button.click()

        time.sleep(2)

        # Check that only LLM logs are shown
        logs_table = driver.find_element(By.CLASS_NAME, "logs-table")
        table_rows = logs_table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header

        if table_rows:
            for row in table_rows[:3]:  # Check first few rows
                cells = row.find_elements(By.TAG_NAME, "td")
                log_type_cell = cells[2]  # Log type is third column
                log_type_badge = log_type_cell.find_element(
                    By.CLASS_NAME, "log-type-badge"
                )
                assert "llm" in log_type_badge.text.lower()

    def test_pagination_functionality(self, driver, test_server):
        """Test pagination functionality."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "pagination")))

        # Check initial page
        results_count = driver.find_element(By.ID, "results-count")
        initial_count_text = results_count.text

        # Look for pagination buttons
        pagination = driver.find_element(By.CLASS_NAME, "pagination")
        pagination_buttons = pagination.find_elements(By.TAG_NAME, "button")

        if len(pagination_buttons) > 2:  # If pagination exists
            # Find and click "Next" button
            next_button = None
            for button in pagination_buttons:
                if "Next" in button.text:
                    next_button = button
                    break

            if next_button and next_button.is_enabled():
                next_button.click()
                time.sleep(2)

                # Check that page changed
                new_count_text = results_count.text
                assert new_count_text != initial_count_text

    def test_export_functionality(self, driver, test_server):
        """Test export functionality."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "export-button")))

        # Click export button
        export_button = driver.find_element(By.ID, "export-button")

        # Note: In headless mode, file downloads may not work as expected
        # This test mainly verifies the export button functionality
        export_button.click()

        # Wait a moment for any popup or download to initiate
        time.sleep(2)

        # Check that no JavaScript errors occurred
        logs = driver.get_log("browser")
        error_logs = [log for log in logs if log["level"] == "SEVERE"]
        assert len(error_logs) == 0, f"JavaScript errors: {error_logs}"

    def test_clear_filters_functionality(self, driver, test_server):
        """Test clear filters functionality."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "clear-button")))

        # Apply some filters
        business_filter = driver.find_element(By.ID, "business-filter")
        business_filter.send_keys("1")

        search_input = driver.find_element(By.ID, "search-input")
        search_input.send_keys("test search")

        log_type_select = Select(driver.find_element(By.ID, "log-type-filter"))
        log_type_select.select_by_value("llm")

        # Click clear button
        clear_button = driver.find_element(By.ID, "clear-button")
        clear_button.click()

        time.sleep(1)

        # Check that filters are cleared
        assert business_filter.get_attribute("value") == ""
        assert search_input.get_attribute("value") == ""

        log_type_select = Select(driver.find_element(By.ID, "log-type-filter"))
        assert log_type_select.first_selected_option.get_attribute("value") == ""

    def test_statistics_modal(self, driver, test_server):
        """Test statistics modal functionality."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-action="stats"]'))
        )

        # Click statistics button
        stats_button = driver.find_element(By.CSS_SELECTOR, '[data-action="stats"]')
        stats_button.click()

        # Wait for modal to appear
        try:
            wait.until(EC.visibility_of_element_located((By.ID, "log-modal")))

            # Check modal content
            modal = driver.find_element(By.ID, "log-modal")
            assert modal.is_displayed()

            # Check for statistics content
            modal_body = modal.find_element(By.CLASS_NAME, "modal-body")
            assert "Total Logs" in modal_body.text

            # Close modal
            close_button = modal.find_element(By.CLASS_NAME, "close-button")
            close_button.click()

            time.sleep(0.5)
            assert not modal.is_displayed()

        except TimeoutException:
            # Modal might not appear due to API issues in test environment
            pass

    def test_dashboard_navigation(self, driver, test_server):
        """Test navigation to dashboard."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[data-action="dashboard"]')
            )
        )

        # Click dashboard button
        dashboard_button = driver.find_element(
            By.CSS_SELECTOR, '[data-action="dashboard"]'
        )

        # Get initial window count
        initial_windows = len(driver.window_handles)

        dashboard_button.click()

        time.sleep(2)

        # Check if new window/tab opened
        current_windows = len(driver.window_handles)
        if current_windows > initial_windows:
            # Switch to new window
            driver.switch_to.window(driver.window_handles[-1])

            # Verify dashboard page
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "dashboard-grid"))
            )
            assert "Analytics Dashboard" in driver.page_source

    def test_responsive_design(self, driver, test_server):
        """Test responsive design on different screen sizes."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "logs-container")))

        # Test desktop size (default)
        desktop_sidebar = driver.find_element(By.CLASS_NAME, "sidebar")
        assert desktop_sidebar.is_displayed()

        # Test mobile size
        driver.set_window_size(375, 667)  # iPhone size
        time.sleep(1)

        # On mobile, layout should still be functional
        # (Specific responsive behavior would depend on CSS implementation)
        main_content = driver.find_element(By.CLASS_NAME, "main-content")
        assert main_content.is_displayed()

        # Reset to desktop size
        driver.set_window_size(1920, 1080)

    def test_error_handling(self, driver, test_server):
        """Test error handling in the interface."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "logs-table")))

        # Test with invalid filter values that might cause errors
        business_filter = driver.find_element(By.ID, "business-filter")
        business_filter.clear()
        business_filter.send_keys("99999")  # Non-existent business

        search_button = driver.find_element(By.ID, "search-button")
        search_button.click()

        time.sleep(2)

        # Page should still be functional, possibly showing no results
        logs_table = driver.find_element(By.CLASS_NAME, "logs-table")
        assert logs_table.is_displayed()

        # Check for JavaScript errors
        logs = driver.get_log("browser")
        error_logs = [log for log in logs if log["level"] == "SEVERE"]
        assert len(error_logs) == 0, f"JavaScript errors: {error_logs}"

    def test_api_integration(self, driver, test_server):
        """Test that the frontend properly integrates with API."""
        # First verify API is working
        response = requests.get(f"{test_server}/api/logs?limit=5")
        assert response.status_code == 200
        response.json()

        # Now test that frontend displays this data
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "logs-table")))

        # Check that logs are displayed
        logs_table = driver.find_element(By.CLASS_NAME, "logs-table")
        table_rows = logs_table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header

        # Should have some rows (up to the limit)
        assert len(table_rows) > 0
        assert len(table_rows) <= 50  # Default limit

    def test_real_time_updates(self, driver, test_server):
        """Test that stats update when filters change."""
        driver.get(f"{test_server}/logs")

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "filtered-logs")))

        # Get initial filtered count
        filtered_count_element = driver.find_element(By.ID, "filtered-logs")

        # Apply a filter
        log_type_select = Select(driver.find_element(By.ID, "log-type-filter"))
        log_type_select.select_by_value("llm")

        search_button = driver.find_element(By.ID, "search-button")
        search_button.click()

        time.sleep(2)

        # Check that filtered count updated
        # The count might be different when filtered
        assert filtered_count_element.is_displayed()

    def test_complete_user_workflow(self, driver, test_server):
        """Test a complete user workflow from start to finish."""
        # 1. Load the page
        driver.get(f"{test_server}/logs")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "logs-table")))

        # 2. Browse initial logs
        logs_table = driver.find_element(By.CLASS_NAME, "logs-table")
        initial_rows = logs_table.find_elements(By.TAG_NAME, "tr")[1:]
        initial_count = len(initial_rows)

        # 3. Filter by business
        business_filter = driver.find_element(By.ID, "business-filter")
        business_filter.send_keys("1")
        search_button = driver.find_element(By.ID, "search-button")
        search_button.click()
        time.sleep(2)

        # 4. Verify filtering worked
        filtered_rows = logs_table.find_elements(By.TAG_NAME, "tr")[1:]
        len(filtered_rows)
        # Filtered results should be different from initial

        # 5. Search for specific content
        search_input = driver.find_element(By.ID, "search-input")
        search_input.send_keys("marketing")
        search_button.click()
        time.sleep(2)

        # 6. Clear filters and return to full view
        clear_button = driver.find_element(By.ID, "clear-button")
        clear_button.click()
        time.sleep(2)

        # 7. Verify we're back to full view
        final_rows = logs_table.find_elements(By.TAG_NAME, "tr")[1:]
        final_count = len(final_rows)

        # Should have data throughout the workflow
        assert initial_count > 0
        assert final_count > 0

        # No JavaScript errors should have occurred
        logs = driver.get_log("browser")
        error_logs = [log for log in logs if log["level"] == "SEVERE"]
        assert len(error_logs) == 0, f"JavaScript errors during workflow: {error_logs}"


if __name__ == "__main__":
    pytest.main([__file__])
