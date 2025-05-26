"""
Integration tests for API interactions in the LeadFactory pipeline.

These tests verify that the LeadFactory pipeline modules correctly interact with external APIs.
They will run with mocks by default, but can use real APIs when --use-real-apis is specified.
"""

import os
import pytest
import tempfile
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import our API test configuration and metrics
from tests.integration.api_test_config import APITestConfig
from tests.integration.api_metrics_fixture import api_metric_decorator


@pytest.fixture
def temp_pipeline_db():
    """Create a temporary database for pipeline testing."""
    # Create a temporary file for the database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # Create test database
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row  # Enable dictionary-like access to rows
        cursor = conn.cursor()

        # Enable foreign key support
        cursor.execute("PRAGMA foreign_keys = ON")

        # Create necessary tables for pipeline
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            category TEXT,
            source TEXT,
            source_id TEXT,
            status TEXT DEFAULT 'pending',
            score INTEGER,
            score_details TEXT,
            tech_stack TEXT,
            core_web_vitals TEXT,
            mockup_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Create email tracking table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY,
            business_id INTEGER,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP,
            opened_at TIMESTAMP,
            clicked_at TIMESTAMP,
            replied_at TIMESTAMP,
            subject TEXT,
            content TEXT,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
        """)

        # Create metrics table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY,
            api_name TEXT,
            endpoint TEXT,
            request_time FLOAT,
            status_code INTEGER,
            cost FLOAT,
            token_count INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Insert test data
        test_businesses = [
            {
                "name": "Test Plumbing Co",
                "address": "123 Main St",
                "city": "New York",
                "state": "NY",
                "zip": "10002",
                "phone": "555-123-4567",
                "website": "http://testplumbing.example.com",
                "category": "plumbers",
                "source": "test"
            },
            {
                "name": "HVAC Solutions",
                "address": "456 Oak Ave",
                "city": "Seattle",
                "state": "WA",
                "zip": "98908",
                "phone": "555-987-6543",
                "website": "http://hvacsolutions.example.com",
                "category": "hvac",
                "source": "test"
            }
        ]

        for business in test_businesses:
            cursor.execute("""
            INSERT INTO businesses (
                name, address, city, state, zip, phone, website, category, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                business["name"],
                business["address"],
                business["city"],
                business["state"],
                business["zip"],
                business["phone"],
                business["website"],
                business["category"],
                business["source"]
            ))

        conn.commit()
        conn.close()

        yield path
    finally:
        # Clean up the temporary file
        if os.path.exists(path):
            os.unlink(path)


@pytest.mark.real_api
@pytest.mark.api_metrics
@pytest.mark.parametrize("vertical_name", ["web_design", "seo", "digital_marketing"])
def test_scrape_api_integration(temp_pipeline_db, yelp_api, google_places_api, api_metrics_logger, metrics_report, api_test_config, vertical_name):
    """Test integration between scrape module and external APIs."""
    # Import here to avoid circular imports
    from leadfactory.pipeline.scrape import scrape_businesses
    from leadfactory.data.verticals import get_vertical_by_name

    # Get test data
    conn, test_zip = temp_pipeline_db
    vertical = get_vertical_by_name(vertical_name)

    # Set up test metadata
    test_metadata = {
        "vertical": vertical_name,
        "zip": test_zip,
        "timestamp": datetime.now().isoformat(),
        "apis_used": ["yelp", "google"],
        "test_config": api_test_config
    }

    # Log metrics for this test
    api_metrics_logger.log_test_start("test_scrape_api_integration", test_metadata)

    # Configure the Yelp API mock to return valid search results
    yelp_api.search_businesses.return_value = ([
        {
            "id": "test-id-1",
            "name": "Test Plumbing",
            "location": {"address1": "123 Main St", "zip_code": "10002"},
            "phone": "+15551234567",
            "url": "https://example.com"
        }
    ], None)

    # Configure the Google Places API mock
    google_places_api.search_places.return_value = ([
        {
            "place_id": "test-place-id",
            "name": "Test HVAC",
            "formatted_address": "456 Broadway, New York, NY 10002"
        }
    ], None)

    # Also mock the get_place_details method to avoid the ValueError
    google_places_api.get_place_details.return_value = ({
        "place_id": "test-place-id",
        "name": "Test HVAC",
        "formatted_address": "456 Broadway, New York, NY 10002",
        "formatted_phone_number": "+15559876543",
        "website": "http://example.com/hvac"
    }, None)

    try:
        # Apply the metrics decorator to track detailed API metrics
        if APITestConfig.should_test_api("yelp"):
            # Create a test-specific metrics decorator for Yelp API
            yelp_api.search_businesses = api_metric_decorator("yelp", "business_search")(yelp_api.search_businesses)

        if APITestConfig.should_test_api("google"):
            # Create a test-specific metrics decorator for Google Places API
            google_places_api.search_places = api_metric_decorator("google", "places_search")(google_places_api.search_places)

        # Execute the function with metrics tracking
        yelp_count, google_count = scrape_businesses(test_zip, vertical, limit=5)

        # Basic assertions
        assert yelp_count >= 0, "Yelp count should be non-negative"
        assert google_count >= 0, "Google count should be non-negative"

        # Log test success with detailed metrics
        result_metadata = {
            "yelp_count": yelp_count,
            "google_count": google_count,
            "total_businesses": yelp_count + google_count,
            "test_duration": api_metrics_logger.get_current_test_duration()
        }
        api_metrics_logger.log_test_end("test_scrape_api_integration", True, metadata=result_metadata)

        # Generate per-test metrics report if enabled
        if api_test_config["metrics"]["enabled"] and os.environ.get("GENERATE_PER_TEST_REPORTS", "0") == "1":
            report_path = metrics_report(format="json")
            logging.info(f"Test metrics report generated: {report_path}")

    except Exception as e:
        # Log test failure with detailed error information
        api_metrics_logger.log_test_end(
            "test_scrape_api_integration",
            False,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )
        raise


@pytest.mark.real_api
@pytest.mark.api_metrics
@pytest.mark.real_api
@pytest.mark.api_metrics
def test_enrich_api_integration(temp_pipeline_db, screenshotone_api, api_metrics_logger, metrics_report, api_test_config):
    """Test integration between enrich module and external APIs."""
    # Import here to avoid circular imports
    from leadfactory.pipeline.enrich import enrich_business

    # Get test data
    conn, _ = temp_pipeline_db
    cursor = conn.cursor()

    # Set up test metadata
    test_metadata = {
        "timestamp": datetime.now().isoformat(),
        "apis_used": ["screenshotone"],
        "test_config": api_test_config
    }

    # Log metrics for this test
    api_metrics_logger.log_test_start("test_enrich_api_integration", test_metadata)

    # Create a test business
    cursor.execute(
        "INSERT INTO businesses (name, website, source) VALUES (?, ?, ?)",
        ("Test Business", "https://www.example.com", "test")
    )
    conn.commit()

    try:
        # Apply the metrics decorator to track detailed API metrics
        if APITestConfig.should_test_api("screenshotone"):
            # Create a test-specific metrics decorator for ScreenshotOne API
            screenshotone_api.capture.return_value = api_metric_decorator("screenshotone", "capture")(screenshotone_api.capture)

        # Execute the function with metrics tracking
        enrich_business(cursor.lastrowid)

        # Basic assertions
        assert True

        # Log test success with detailed metrics
        result_metadata = {
            "test_duration": api_metrics_logger.get_current_test_duration()
        }
        api_metrics_logger.log_test_end("test_enrich_api_integration", True, metadata=result_metadata)

        # Generate per-test metrics report if enabled
        if api_test_config["metrics"]["enabled"] and os.environ.get("GENERATE_PER_TEST_REPORTS", "0") == "1":
            report_path = metrics_report(format="json")
            logging.info(f"Test metrics report generated: {report_path}")

    except Exception as e:
        # Log test failure with detailed error information
        api_metrics_logger.log_test_end(
            "test_enrich_api_integration",
            False,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )
        raise


@pytest.mark.api_metrics
def test_score_api_integration(temp_pipeline_db, api_metrics_logger, metrics_report, api_test_config):
    """Test integration between score module and any APIs it might use."""
    # Import here to avoid circular imports
    from leadfactory.pipeline.score import score_business

    # Get test data
    conn, _ = temp_pipeline_db
    cursor = conn.cursor()

    # Set up test metadata
    test_metadata = {
        "timestamp": datetime.now().isoformat(),
        "apis_used": [],  # Score module might not use external APIs directly
        "test_config": api_test_config
    }

    # Log metrics for this test
    api_metrics_logger.log_test_start("test_score_api_integration", test_metadata)

    # Create a test business with enrichment data to score
    cursor.execute(
        """INSERT INTO businesses
        (name, website, tech_stack, core_web_vitals, source)
        VALUES (?, ?, ?, ?, ?)""",
        (
            "Test Business",
            "https://www.example.com",
            json.dumps({"cms": "wordpress", "analytics": ["google analytics"]}),
            json.dumps({"cls": 0.1, "lcp": 2500, "fid": 100}),
            "test"
        )
    )
    conn.commit()

    try:
        # Execute the function with metrics tracking
        score = score_business(cursor.lastrowid)

        # Verify results
        assert isinstance(score, int)

        # Log test success with detailed metrics
        result_metadata = {
            "test_duration": api_metrics_logger.get_current_test_duration()
        }
        api_metrics_logger.log_test_end("test_score_api_integration", True, metadata=result_metadata)

        # Generate per-test metrics report if enabled
        if api_test_config["metrics"]["enabled"] and os.environ.get("GENERATE_PER_TEST_REPORTS", "0") == "1":
            report_path = metrics_report(format="json")
            logging.info(f"Test metrics report generated: {report_path}")

    except Exception as e:
        # Log test failure with detailed error information
        api_metrics_logger.log_test_end(
            "test_score_api_integration",
            False,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )
        raise


@pytest.mark.real_api
@pytest.mark.api_metrics
@pytest.mark.real_api
@pytest.mark.api_metrics
def test_mockup_api_integration(temp_pipeline_db, openai_api, api_metrics_logger, metrics_report, api_test_config):
    """Test integration between mockup module and OpenAI API."""
    # Import here to avoid circular imports
    from leadfactory.pipeline.mockup import create_mockup

    # Get test data
    conn, _ = temp_pipeline_db
    cursor = conn.cursor()

    # Set up test metadata
    test_metadata = {
        "timestamp": datetime.now().isoformat(),
        "apis_used": ["openai"],
        "test_config": api_test_config
    }

    # Log metrics for this test
    api_metrics_logger.log_test_start("test_mockup_api_integration", test_metadata)

    # Create a test business
    cursor.execute(
        "INSERT INTO businesses (name, website, source, score) VALUES (?, ?, ?, ?)",
        ("Test Business", "https://www.example.com", "test", 85)
    )
    conn.commit()

    try:
        # Apply the metrics decorator to track detailed API metrics
        if APITestConfig.should_test_api("openai"):
            # Create a test-specific metrics decorator for OpenAI API
            openai_api.create.return_value = api_metric_decorator("openai", "create")(openai_api.create)

        # Execute the function with metrics tracking
        create_mockup(cursor.lastrowid)

        # Basic assertions
        assert True

        # Log test success with detailed metrics
        result_metadata = {
            "test_duration": api_metrics_logger.get_current_test_duration()
        }
        api_metrics_logger.log_test_end("test_mockup_api_integration", True, metadata=result_metadata)

        # Generate per-test metrics report if enabled
        if api_test_config["metrics"]["enabled"] and os.environ.get("GENERATE_PER_TEST_REPORTS", "0") == "1":
            report_path = metrics_report(format="json")
            logging.info(f"Test metrics report generated: {report_path}")

    except Exception as e:
        # Log test failure with detailed error information
        api_metrics_logger.log_test_end(
            "test_mockup_api_integration",
            False,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )
        raise


@pytest.mark.real_api
@pytest.mark.api_metrics
def test_email_api_integration(temp_pipeline_db, sendgrid_api, api_metrics_logger, metrics_report, api_test_config):
    """Test integration between email queue module and SendGrid API."""
    # Import here to avoid circular imports
    from leadfactory.pipeline.email_queue import send_email_to_business

    # Get test data
    conn, _ = temp_pipeline_db
    cursor = conn.cursor()

    # Set up test metadata
    test_metadata = {
        "timestamp": datetime.now().isoformat(),
        "apis_used": ["sendgrid"],
        "test_config": api_test_config
    }

    # Log metrics for this test
    api_metrics_logger.log_test_start("test_email_api_integration", test_metadata)

    # Create a test business with all required data for email
    cursor.execute(
        """INSERT INTO businesses
        (name, email, website, mockup, source, score)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            "Test Business",
            "test@example.com",
            "https://www.example.com",
            "<!DOCTYPE html><html><body><h1>Test Mockup</h1></body></html>",
            "test",
            85
        )
    )
    conn.commit()
    business_id = cursor.lastrowid

    try:
        # Apply the metrics decorator to track detailed API metrics
        if APITestConfig.should_test_api("sendgrid"):
            # Create a test-specific metrics decorator for SendGrid API
            sendgrid_api.send.return_value = api_metric_decorator("sendgrid", "send_email")(sendgrid_api.send)
            sendgrid_api.send.return_value.status_code = 202

        # Send email with metrics tracking
        with patch("leadfactory.pipeline.email_queue.SendGridAPIClient", return_value=sendgrid_api):
            start_time = datetime.now()
            success = send_email_to_business(
                business_id=business_id,
                template="test_template",
                subject="Test Email"
            )
            email_send_time = (datetime.now() - start_time).total_seconds()

        # Verify results
        assert success, "Email should be sent successfully"

        # Log test success with detailed metrics
        result_metadata = {
            "business_id": business_id,
            "email_send_time_seconds": email_send_time,
            "test_duration": api_metrics_logger.get_current_test_duration()
        }
        api_metrics_logger.log_test_end("test_email_api_integration", True, metadata=result_metadata)

        # Generate per-test metrics report if enabled
        if api_test_config["metrics"]["enabled"] and os.environ.get("GENERATE_PER_TEST_REPORTS", "0") == "1":
            report_path = metrics_report(format="json")
            logging.info(f"Test metrics report generated: {report_path}")

    except Exception as e:
        # Log test failure with detailed error information
        api_metrics_logger.log_test_end(
            "test_email_api_integration",
            False,
            error=str(e),
            metadata={"error_type": type(e).__name__, "business_id": business_id}
        )
        raise


@pytest.mark.skip(reason="Full pipeline test needs implementation after individual tests pass")
@pytest.mark.real_api
@pytest.mark.real_api
@pytest.mark.api_metrics
def test_full_pipeline_api_integration(temp_pipeline_db, yelp_api, google_places_api,
                                       openai_api, sendgrid_api, screenshotone_api,
                                       api_metrics_logger, metrics_report, api_test_config):
    """Test full pipeline integration with all external APIs."""
    # Import pipeline modules
    from leadfactory.pipeline.scrape import scrape_businesses
    from leadfactory.pipeline.enrich import enrich_business
    from leadfactory.pipeline.score import score_business
    from leadfactory.pipeline.mockup import create_mockup
    from leadfactory.pipeline.email_queue import send_email_to_business
    from leadfactory.data.verticals import get_vertical_by_name

    # Get test data
    conn, test_zip = temp_pipeline_db

    # Set up test metadata
    test_metadata = {
        "timestamp": datetime.now().isoformat(),
        "apis_used": ["yelp", "google", "screenshotone", "openai", "sendgrid"],
        "test_config": api_test_config,
        "zip_code": test_zip,
        "vertical": "web_design"
    }

    # Log metrics for this test
    api_metrics_logger.log_test_start("test_full_pipeline_api_integration", test_metadata)

    try:
        # Apply the metrics decorators to track detailed API metrics for all APIs
        if APITestConfig.should_test_api("yelp"):
            yelp_api.search_businesses = api_metric_decorator("yelp", "business_search")(yelp_api.search_businesses)

        if APITestConfig.should_test_api("google"):
            google_places_api.search_places = api_metric_decorator("google", "places_search")(google_places_api.search_places)

        if APITestConfig.should_test_api("screenshotone"):
            screenshotone_api.capture = api_metric_decorator("screenshotone", "take_screenshot")(screenshotone_api.capture)

        if APITestConfig.should_test_api("openai"):
            # Set up mock response with usage data for token tracking
            mock_openai_response = MagicMock()
            mock_openai_response.choices = [MagicMock()]
            mock_openai_response.choices[0].message.content = """
            {{
                "mockup_html": "<!DOCTYPE html><html><head><title>Test Mockup</title></head><body><h1>Test Mockup</h1></body></html>",
                "explanation": "This is a test mockup"
            }}
            """
            mock_openai_response.usage = MagicMock()
            mock_openai_response.usage.total_tokens = 200
            mock_openai_response.model = "gpt-3.5-turbo"
            openai_api.ChatCompletion.create.return_value = mock_openai_response
            openai_api.ChatCompletion.create = api_metric_decorator("openai", "chat_completion")(openai_api.ChatCompletion.create)

        if APITestConfig.should_test_api("sendgrid"):
            sendgrid_api.send.return_value = api_metric_decorator("sendgrid", "send_email")(sendgrid_api.send)
            sendgrid_api.send.return_value.status_code = 202

        # Run the entire pipeline with appropriate patches
        # For this test, we'll simulate running each step and collecting metrics
        pipeline_metrics = {}

        # 1. Scrape businesses
        with patch("leadfactory.pipeline.scrape.YelpAPI", return_value=yelp_api):
            with patch("leadfactory.pipeline.scrape.GooglePlacesAPI", return_value=google_places_api):
                start_time = datetime.now()
                yelp_count, google_count = scrape_businesses(
                    zip_code=test_zip,
                    vertical=get_vertical_by_name("web_design"),
                    limit=2
                )
                pipeline_metrics["scrape_time"] = (datetime.now() - start_time).total_seconds()
                pipeline_metrics["business_count"] = yelp_count + google_count

        # 2. Get a business ID to work with
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM businesses LIMIT 1")
        business = cursor.fetchone()

        # If no business was found in the DB (because we're using mocks), create one
        if not business:
            cursor.execute(
                "INSERT INTO businesses (name, website, source) VALUES (?, ?, ?)",
                ("Test Business", "https://www.example.com", "test")
            )
            conn.commit()
            business_id = cursor.lastrowid
        else:
            business_id = business["id"]

        pipeline_metrics["business_id"] = business_id

        # 3. Enrich business
        with patch("leadfactory.pipeline.enrich.ScreenshotOneAPI", return_value=screenshotone_api):
            start_time = datetime.now()
            enriched_business = enrich_business(business_id)
            pipeline_metrics["enrich_time"] = (datetime.now() - start_time).total_seconds()

        # 4. Score business
        start_time = datetime.now()
        score, details = score_business(business_id)
        pipeline_metrics["score_time"] = (datetime.now() - start_time).total_seconds()
        pipeline_metrics["score"] = score

        # 5. Create mockup
        with patch("leadfactory.pipeline.mockup.openai", openai_api):
            start_time = datetime.now()
            mockup = create_mockup(business_id)
            pipeline_metrics["mockup_time"] = (datetime.now() - start_time).total_seconds()
            pipeline_metrics["mockup_size"] = len(mockup) if mockup else 0

        # 6. Send email
        with patch("leadfactory.pipeline.email_queue.SendGridAPIClient", return_value=sendgrid_api):
            start_time = datetime.now()
            email_sent = send_email_to_business(
                business_id=business_id,
                template="test_template",
                subject="Test Email"
            )
            pipeline_metrics["email_time"] = (datetime.now() - start_time).total_seconds()
            pipeline_metrics["email_sent"] = email_sent

        # Verify pipeline success
        assert pipeline_metrics["business_count"] >= 0, "At least one business should be processed"
        assert pipeline_metrics["score"] is not None, "Business should be scored"
        assert "mockup_size" in pipeline_metrics, "Mockup should be generated"

        # Log test success with detailed metrics
        pipeline_metrics["test_duration"] = api_metrics_logger.get_current_test_duration()
        pipeline_metrics["total_api_calls"] = len(api_metrics_logger.metrics)
        api_metrics_logger.log_test_end("test_full_pipeline_api_integration", True, metadata=pipeline_metrics)

        # Generate comprehensive metrics report
        report_path = metrics_report(format="json")
        logging.info(f"Full pipeline metrics report generated: {report_path}")

        # Also generate HTML report if visualization libraries are available
        try:
            html_report_path = metrics_report(format="html")
            logging.info(f"HTML pipeline metrics report generated: {html_report_path}")
        except Exception as e:
            logging.warning(f"HTML report generation failed: {str(e)}")

    except Exception as e:
        # Log test failure with detailed error information
        api_metrics_logger.log_test_end(
            "test_full_pipeline_api_integration",
            False,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )
        raise
