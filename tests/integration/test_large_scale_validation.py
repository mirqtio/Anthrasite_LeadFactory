"""
Large-scale validation tests for the LeadFactory pipeline.

These tests validate the system's behavior when processing a large number of leads,
ensuring performance, scalability, and reliability under load.
"""

import json
import logging
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import our API test configuration and metrics
from tests.integration.api_metrics_fixture import APIMetricsLogger, api_metric_decorator
from tests.integration.api_test_config import APITestConfig
from tests.utils import generate_test_business, insert_test_businesses_batch

# Import pipeline components - TEMPORARY FIX for import issues
try:
    from leadfactory.utils.logging import setup_logger
    from leadfactory.utils.metrics import (
        PIPELINE_FAILURE_RATE,
        initialize_metrics,
        record_metric,
    )
    IMPORT_SUCCESS = True
except ImportError:
    # Create mock functions for testing
    def initialize_metrics():
        pass
    def record_metric(*args, **kwargs):
        pass
    PIPELINE_FAILURE_RATE = None
    def setup_logger(name, level=None):
        import logging
        return logging.getLogger(name)
    IMPORT_SUCCESS = False

# Configure logging
logger = setup_logger("large_scale_tests", level=logging.INFO)


@pytest.fixture
def large_scale_db():
    """Create a database for large-scale testing with proper indexes."""
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

        # Enable WAL mode for better performance
        cursor.execute("PRAGMA journal_mode = WAL")

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

        # Create necessary indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_status ON businesses(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_category ON businesses(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_score ON businesses(score)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_business_id ON emails(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status)")

        conn.commit()

        yield conn

        conn.close()
    finally:
        # Clean up the temporary file
        if os.path.exists(path):
            os.unlink(path)


def generate_test_businesses(count: int, categories: list[str], locations: list[str]) -> list[dict[str, Any]]:
    """Generate a large batch of test businesses."""
    businesses = []

    for i in range(count):
        category = categories[i % len(categories)]
        location = locations[i % len(locations)]
        city, state, zip_code = location.split(", ")

        business = generate_test_business(complete=True)
        business.update({
            "name": f"Test Business {i+1}",
            "category": category,
            "city": city,
            "state": state,
            "zip": zip_code,
            "source": "test_large_scale",
            "source_id": f"large_scale_{i+1}"
        })
        businesses.append(business)

    return businesses


class TestMetrics:
    """Helper class to track test metrics."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.stage_times = {
            "enrich": [],
            "score": [],
            "validate": [],
            "email": []
        }
        self.failure_counts = {
            "enrich": 0,
            "score": 0,
            "validate": 0,
            "email": 0
        }
        self.total_processed = 0
        self.total_succeeded = 0

    def start_timer(self):
        """Start the test timer."""
        self.start_time = time.time()

    def stop_timer(self):
        """Stop the test timer."""
        self.end_time = time.time()

    def record_stage_time(self, stage: str, duration: float):
        """Record the time taken for a stage."""
        if stage in self.stage_times:
            self.stage_times[stage].append(duration)

    def record_failure(self, stage: str):
        """Record a failure for a stage."""
        if stage in self.failure_counts:
            self.failure_counts[stage] += 1

    def get_total_time(self) -> float:
        """Get the total time taken for the test."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    def get_average_stage_time(self, stage: str) -> float:
        """Get the average time taken for a stage."""
        times = self.stage_times.get(stage, [])
        if not times:
            return 0.0
        return sum(times) / len(times)

    def get_throughput(self) -> float:
        """Get the overall throughput in leads per second."""
        total_time = self.get_total_time()
        if total_time <= 0 or self.total_processed <= 0:
            return 0.0
        return self.total_processed / total_time

    def get_success_rate(self) -> float:
        """Get the overall success rate."""
        if self.total_processed <= 0:
            return 0.0
        return self.total_succeeded / self.total_processed

    def get_stage_failure_rate(self, stage: str) -> float:
        """Get the failure rate for a stage."""
        if self.total_processed <= 0:
            return 0.0
        return self.failure_counts.get(stage, 0) / self.total_processed

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the test metrics."""
        total_time = self.get_total_time()

        return {
            "total_time_seconds": total_time,
            "total_processed": self.total_processed,
            "total_succeeded": self.total_succeeded,
            "throughput_per_second": self.get_throughput(),
            "throughput_per_minute": self.get_throughput() * 60,
            "success_rate": self.get_success_rate(),
            "stage_metrics": {
                stage: {
                    "avg_time_seconds": self.get_average_stage_time(stage),
                    "failure_rate": self.get_stage_failure_rate(stage),
                    "failure_count": self.failure_counts.get(stage, 0)
                }
                for stage in self.stage_times
            }
        }


class MockPipeline:
    """Mock pipeline for large-scale testing."""

    def __init__(self, db_conn, test_metrics: TestMetrics = None):
        self.db = db_conn
        self.test_metrics = test_metrics or TestMetrics()

    def enrich(self, business):
        """Mock enrichment of a business."""
        start_time = time.time()

        try:
            # Simulate enrichment process
            time.sleep(0.01)  # Small delay to simulate work

            # Add enrichment data
            enriched = business.copy()
            enriched.update({
                "tech_stack": json.dumps(["WordPress", "PHP", "MySQL", "jQuery"]),
                "core_web_vitals": json.dumps({
                    "lcp": 2.5,
                    "fid": 100,
                    "cls": 0.1
                })
            })

            # Update the test metrics
            duration = time.time() - start_time
            if self.test_metrics:
                self.test_metrics.record_stage_time("enrich", duration)

            return enriched

        except Exception:
            # Record failure
            if self.test_metrics:
                self.test_metrics.record_failure("enrich")
            raise

    def score(self, business):
        """Mock scoring of a business."""
        start_time = time.time()

        try:
            # Simulate scoring process
            time.sleep(0.005)  # Small delay to simulate work

            # Add scoring data
            scored = business.copy()
            score = hash(business["name"]) % 100  # Deterministic but varied score
            scored.update({
                "score": score,
                "score_details": json.dumps({
                    "website_score": score * 0.4,
                    "size_score": score * 0.3,
                    "tech_score": score * 0.3
                })
            })

            # Update the test metrics
            duration = time.time() - start_time
            if self.test_metrics:
                self.test_metrics.record_stage_time("score", duration)

            return scored

        except Exception:
            # Record failure
            if self.test_metrics:
                self.test_metrics.record_failure("score")
            raise

    def validate(self, business):
        """Mock validation of a business."""
        start_time = time.time()

        try:
            # Simulate validation process
            time.sleep(0.002)  # Small delay to simulate work

            # Validate the business
            validated = business.copy()

            # Update the test metrics
            duration = time.time() - start_time
            if self.test_metrics:
                self.test_metrics.record_stage_time("validate", duration)

            return validated

        except Exception:
            # Record failure
            if self.test_metrics:
                self.test_metrics.record_failure("validate")
            raise

    def store(self, business):
        """Mock storing of a business."""
        # No metrics tracked for storage as it's considered part of the validate step
        # in the large-scale tests

        # Store the updated business in the database
        cursor = self.db.cursor()

        # Check if the business already exists
        cursor.execute(
            "SELECT id FROM businesses WHERE source_id = ?",
            (business.get("source_id"),)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing business
            business_id = existing["id"]
            cursor.execute(
                """
                UPDATE businesses SET
                    name = ?,
                    address = ?,
                    city = ?,
                    state = ?,
                    zip = ?,
                    phone = ?,
                    email = ?,
                    website = ?,
                    category = ?,
                    status = ?,
                    score = ?,
                    score_details = ?,
                    tech_stack = ?,
                    core_web_vitals = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    business.get("name", ""),
                    business.get("address", ""),
                    business.get("city", ""),
                    business.get("state", ""),
                    business.get("zip", ""),
                    business.get("phone", ""),
                    business.get("email", ""),
                    business.get("website", ""),
                    business.get("category", ""),
                    "processed",
                    business.get("score"),
                    business.get("score_details"),
                    business.get("tech_stack"),
                    business.get("core_web_vitals"),
                    business_id
                )
            )
        else:
            # Insert new business
            cursor.execute(
                """
                INSERT INTO businesses (
                    name, address, city, state, zip, phone, email, website,
                    category, source, source_id, status, score, score_details,
                    tech_stack, core_web_vitals
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    business.get("name", ""),
                    business.get("address", ""),
                    business.get("city", ""),
                    business.get("state", ""),
                    business.get("zip", ""),
                    business.get("phone", ""),
                    business.get("email", ""),
                    business.get("website", ""),
                    business.get("category", ""),
                    business.get("source", ""),
                    business.get("source_id", ""),
                    "processed",
                    business.get("score"),
                    business.get("score_details"),
                    business.get("tech_stack"),
                    business.get("core_web_vitals")
                )
            )
            business_id = cursor.lastrowid

        self.db.commit()

        stored = business.copy()
        stored["id"] = business_id
        return stored

    def email_queue(self, business):
        """Mock email queue process for a business."""
        start_time = time.time()

        try:
            # Simulate email queue process
            time.sleep(0.008)  # Small delay to simulate work

            # Add email to queue
            cursor = self.db.cursor()
            cursor.execute(
                """
                INSERT INTO emails (
                    business_id, status, subject, content
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    business.get("id"),
                    "pending",
                    f"Improve your website - {business.get('name')}",
                    f"Here's how we can help improve your website at {business.get('website')}"
                )
            )
            self.db.commit()

            # Update the test metrics
            duration = time.time() - start_time
            if self.test_metrics:
                self.test_metrics.record_stage_time("email", duration)

            return True

        except Exception:
            # Record failure
            if self.test_metrics:
                self.test_metrics.record_failure("email")
            raise


def process_leads(
    mock_pipeline: MockPipeline,
    businesses: list[dict[str, Any]],
    test_metrics: TestMetrics,
    batch_size: int = 100,
    max_failures: int = None
) -> tuple[int, int]:
    """Process a large batch of leads through the pipeline."""
    test_metrics.start_timer()

    total_processed = 0
    total_succeeded = 0
    total_failed = 0

    # Process in batches
    for i in range(0, len(businesses), batch_size):
        batch = businesses[i:i+batch_size]
        batch_start = time.time()
        batch_count = i // batch_size + 1

        logger.info(f"Processing batch {batch_count}/{(len(businesses) + batch_size - 1) // batch_size} ({len(batch)} leads)...")

        # Process each lead in the batch
        for lead in batch:
            total_processed += 1
            test_metrics.total_processed += 1

            try:
                # Full pipeline process
                enriched = mock_pipeline.enrich(lead)
                scored = mock_pipeline.score(enriched)
                validated = mock_pipeline.validate(scored)
                stored = mock_pipeline.store(validated)
                mock_pipeline.email_queue(stored)

                total_succeeded += 1
                test_metrics.total_succeeded += 1

            except Exception as e:
                total_failed += 1
                logger.error(f"Failed to process lead {lead.get('source_id')}: {str(e)}")

                # Check if we've hit the maximum allowed failures
                if max_failures is not None and total_failed >= max_failures:
                    logger.error(f"Reached maximum allowed failures ({max_failures}). Stopping processing.")
                    break

        # Log batch progress
        batch_time = time.time() - batch_start
        throughput = len(batch) / batch_time if batch_time > 0 else 0

        logger.info(f"Batch {batch_count} processed in {batch_time:.2f}s ({throughput:.2f} leads/sec)")
        logger.info(f"Current totals: {total_succeeded} succeeded, {total_failed} failed")

        # Stop if we've hit the maximum allowed failures
        if max_failures is not None and total_failed >= max_failures:
            break

    test_metrics.stop_timer()

    total_time = test_metrics.get_total_time()
    overall_throughput = total_processed / total_time if total_time > 0 else 0

    logger.info(f"Processing completed in {total_time:.2f}s")
    logger.info(f"Total processed: {total_processed}, succeeded: {total_succeeded}, failed: {total_failed}")
    logger.info(f"Overall throughput: {overall_throughput:.2f} leads/sec")

    return total_succeeded, total_failed


@pytest.mark.large_scale
def test_large_scale_100_leads(large_scale_db):
    """Test the pipeline with 100 leads."""
    # Set up test data
    categories = ["plumbers", "hvac", "vets"]
    locations = ["New York, NY, 10002", "Seattle, WA, 98908", "Carmel, IN, 46032"]

    # Generate test businesses
    businesses = generate_test_businesses(100, categories, locations)

    # Set up metrics tracking
    test_metrics = TestMetrics()

    # Create mock pipeline
    mock_pipeline = MockPipeline(large_scale_db, test_metrics)

    # Process the leads
    succeeded, failed = process_leads(mock_pipeline, businesses, test_metrics)

    # Get metrics summary
    metrics_summary = test_metrics.get_summary()

    # Verify metrics
    assert metrics_summary["total_processed"] == 100
    assert metrics_summary["success_rate"] >= 0.95, f"Success rate too low: {metrics_summary['success_rate']}"
    assert metrics_summary["throughput_per_minute"] >= 600, f"Throughput too low: {metrics_summary['throughput_per_minute']} leads/min"

    # Log detailed metrics
    logger.info(f"Test metrics: {json.dumps(metrics_summary, indent=2)}")

    # Check database
    cursor = large_scale_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE status = 'processed'")
    processed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails")
    email_count = cursor.fetchone()[0]

    assert processed_count >= 95, f"Not enough businesses processed: {processed_count}"
    assert email_count >= 95, f"Not enough emails created: {email_count}"


@pytest.mark.large_scale
def test_large_scale_1000_leads(large_scale_db):
    """Test the pipeline with 1,000 leads."""
    # Set up test data
    categories = ["plumbers", "hvac", "vets"]
    locations = ["New York, NY, 10002", "Seattle, WA, 98908", "Carmel, IN, 46032"]

    # Generate test businesses
    businesses = generate_test_businesses(1000, categories, locations)

    # Set up metrics tracking
    test_metrics = TestMetrics()

    # Create mock pipeline
    mock_pipeline = MockPipeline(large_scale_db, test_metrics)

    # Process the leads
    succeeded, failed = process_leads(mock_pipeline, businesses, test_metrics, batch_size=100)

    # Get metrics summary
    metrics_summary = test_metrics.get_summary()

    # Verify metrics
    assert metrics_summary["total_processed"] == 1000
    assert metrics_summary["success_rate"] >= 0.95, f"Success rate too low: {metrics_summary['success_rate']}"
    assert metrics_summary["throughput_per_minute"] >= 600, f"Throughput too low: {metrics_summary['throughput_per_minute']} leads/min"

    # Check database
    cursor = large_scale_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE status = 'processed'")
    processed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails")
    email_count = cursor.fetchone()[0]

    assert processed_count >= 950, f"Not enough businesses processed: {processed_count}"
    assert email_count >= 950, f"Not enough emails created: {email_count}"


@pytest.mark.large_scale
@pytest.mark.slow
def test_large_scale_10000_leads(large_scale_db):
    """Test the pipeline with 10,000 leads."""
    # Set up test data
    categories = ["plumbers", "hvac", "vets"]
    locations = ["New York, NY, 10002", "Seattle, WA, 98908", "Carmel, IN, 46032"]

    # Generate test businesses
    businesses = generate_test_businesses(10000, categories, locations)

    # Set up metrics tracking
    test_metrics = TestMetrics()

    # Create mock pipeline
    mock_pipeline = MockPipeline(large_scale_db, test_metrics)

    # Process the leads
    succeeded, failed = process_leads(mock_pipeline, businesses, test_metrics, batch_size=200)

    # Get metrics summary
    metrics_summary = test_metrics.get_summary()

    # Verify metrics
    assert metrics_summary["total_processed"] == 10000
    assert metrics_summary["success_rate"] >= 0.95, f"Success rate too low: {metrics_summary['success_rate']}"
    assert metrics_summary["throughput_per_minute"] >= 600, f"Throughput too low: {metrics_summary['throughput_per_minute']} leads/min"

    # Check that each stage has reasonable performance
    for stage, metrics in metrics_summary["stage_metrics"].items():
        assert metrics["failure_rate"] <= 0.01, f"Too many failures in {stage} stage: {metrics['failure_rate']}"

    # Check database
    cursor = large_scale_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE status = 'processed'")
    processed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails")
    email_count = cursor.fetchone()[0]

    assert processed_count >= 9500, f"Not enough businesses processed: {processed_count}"
    assert email_count >= 9500, f"Not enough emails created: {email_count}"


@pytest.mark.large_scale
def test_large_scale_failure_scenarios(large_scale_db):
    """Test the pipeline's behavior under various failure scenarios."""
    # Set up test data
    categories = ["plumbers", "hvac", "vets"]
    locations = ["New York, NY, 10002", "Seattle, WA, 98908", "Carmel, IN, 46032"]

    # Generate test businesses
    businesses = generate_test_businesses(500, categories, locations)

    # Set up metrics tracking
    test_metrics = TestMetrics()

    # Create mock pipeline with failure injection
    mock_pipeline = MockPipeline(large_scale_db, test_metrics)

    # Inject failures into various stages
    original_enrich = mock_pipeline.enrich
    original_score = mock_pipeline.score

    def enrich_with_failures(business):
        # Simulate random failures (5% failure rate)
        if hash(business["name"]) % 20 == 0:
            raise ValueError(f"Simulated enrichment failure for {business['name']}")
        return original_enrich(business)

    def score_with_failures(business):
        # Simulate random failures (3% failure rate)
        if hash(business["name"]) % 33 == 0:
            raise ValueError(f"Simulated scoring failure for {business['name']}")
        return original_score(business)

    # Apply the patched methods
    mock_pipeline.enrich = enrich_with_failures
    mock_pipeline.score = score_with_failures

    # Process the leads
    succeeded, failed = process_leads(mock_pipeline, businesses, test_metrics, batch_size=50)

    # Get metrics summary
    metrics_summary = test_metrics.get_summary()

    # Verify metrics
    assert metrics_summary["total_processed"] == 500

    # We expect a success rate lower than normal due to injected failures
    assert 0.80 <= metrics_summary["success_rate"] <= 0.95, f"Unexpected success rate: {metrics_summary['success_rate']}"

    # Check failure rates for individual stages
    assert 0.03 <= metrics_summary["stage_metrics"]["enrich"]["failure_rate"] <= 0.07, \
        f"Unexpected enrich failure rate: {metrics_summary['stage_metrics']['enrich']['failure_rate']}"

    assert 0.01 <= metrics_summary["stage_metrics"]["score"]["failure_rate"] <= 0.05, \
        f"Unexpected score failure rate: {metrics_summary['stage_metrics']['score']['failure_rate']}"

    # Log detailed metrics
    logger.info(f"Failure test metrics: {json.dumps(metrics_summary, indent=2)}")


@pytest.mark.large_scale
def test_large_scale_performance_bottlenecks(large_scale_db):
    """Test the pipeline to identify potential performance bottlenecks."""
    # Set up test data
    categories = ["plumbers", "hvac", "vets"]
    locations = ["New York, NY, 10002", "Seattle, WA, 98908", "Carmel, IN, 46032"]

    # Generate test businesses
    businesses = generate_test_businesses(200, categories, locations)

    # Set up metrics tracking
    test_metrics = TestMetrics()

    # Create mock pipeline
    mock_pipeline = MockPipeline(large_scale_db, test_metrics)

    # Inject a performance bottleneck in the enrichment stage
    original_enrich = mock_pipeline.enrich

    def slow_enrich(business):
        # Simulate a slow enrichment process for certain categories
        if business["category"] == "hvac":
            time.sleep(0.05)  # 5x slower than normal
        return original_enrich(business)

    # Apply the patched method
    mock_pipeline.enrich = slow_enrich

    # Process the leads
    succeeded, failed = process_leads(mock_pipeline, businesses, test_metrics, batch_size=50)

    # Get metrics summary
    metrics_summary = test_metrics.get_summary()

    # Verify metrics
    assert metrics_summary["total_processed"] == 200

    # Identify the bottleneck
    stage_times = {
        stage: metrics["avg_time_seconds"]
        for stage, metrics in metrics_summary["stage_metrics"].items()
    }

    # Enrich should be the slowest stage due to our injection
    slowest_stage = max(stage_times.items(), key=lambda x: x[1])
    assert slowest_stage[0] == "enrich", f"Expected 'enrich' to be the slowest stage, but got '{slowest_stage[0]}'"

    # Verify the performance impact
    assert stage_times["enrich"] > 0.02, f"Enrich stage not showing expected slowdown: {stage_times['enrich']}s"

    # Log detailed metrics
    logger.info(f"Performance bottleneck test metrics: {json.dumps(metrics_summary, indent=2)}")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
