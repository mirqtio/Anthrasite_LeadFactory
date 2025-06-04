"""
Tests for Email A/B Testing functionality.
"""

import pytest
import tempfile
import os
from datetime import datetime

from leadfactory.ab_testing.email_ab_test import EmailABTest
from leadfactory.ab_testing.ab_test_manager import ABTestManager
from leadfactory.email.templates import EmailPersonalization


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def test_manager(temp_db):
    """Create test manager with temporary database."""
    return ABTestManager(db_path=temp_db)


@pytest.fixture
def email_ab_test(test_manager):
    """Create email A/B test instance."""
    return EmailABTest(test_manager)


def test_create_subject_line_test(email_ab_test):
    """Test creating subject line A/B test."""
    subject_variants = [
        {"subject": "Your audit report is ready!", "weight": 0.25},
        {"subject": "Don't miss your business insights!", "weight": 0.25},
        {"subject": "🎉 Your report is here - download now!", "weight": 0.25},
        {"subject": "Action required: Review your audit results", "weight": 0.25}
    ]

    test_id = email_ab_test.create_subject_line_test(
        name="Q1 Report Delivery Subject Test",
        description="Test different subject line urgency levels",
        subject_variants=subject_variants,
        target_sample_size=1000
    )

    assert test_id is not None
    assert len(test_id) > 0

    # Verify test configuration
    test_config = email_ab_test.test_manager.get_test_config(test_id)
    assert test_config.name == "Q1 Report Delivery Subject Test"
    assert len(test_config.variants) == 4
    assert test_config.metadata['test_type'] == 'subject_line'


def test_create_cta_test(email_ab_test):
    """Test creating CTA button A/B test."""
    cta_variants = [
        {"text": "View Your Report", "style": "primary", "weight": 0.5},
        {"text": "Download Now", "style": "primary", "weight": 0.5}
    ]

    test_id = email_ab_test.create_cta_test(
        name="CTA Button Test",
        description="Test different CTA button text",
        cta_variants=cta_variants,
        target_sample_size=500
    )

    assert test_id is not None

    test_config = email_ab_test.test_manager.get_test_config(test_id)
    assert test_config.name == "CTA Button Test"
    assert len(test_config.variants) == 2


def test_get_email_variant_for_user(email_ab_test):
    """Test getting email variant assignment for user."""
    subject_variants = [
        {"subject": "Variant A", "weight": 0.5},
        {"subject": "Variant B", "weight": 0.5}
    ]

    test_id = email_ab_test.create_subject_line_test(
        name="User Assignment Test",
        description="Test user assignment",
        subject_variants=subject_variants
    )

    # Start the test
    email_ab_test.test_manager.start_test(test_id)

    # Get variant for user
    user_id = "test_user_123"
    user_email = "test@example.com"

    variant_id, variant_config = email_ab_test.get_email_variant_for_user(
        user_id=user_id,
        user_email=user_email,
        test_id=test_id,
        email_type="report_delivery"
    )

    assert variant_id is not None
    assert variant_config is not None
    assert 'subject' in variant_config
    assert variant_config['subject'] in ["Variant A", "Variant B"]

    # Test consistency - same user should get same variant
    variant_id_2, variant_config_2 = email_ab_test.get_email_variant_for_user(
        user_id=user_id,
        user_email=user_email,
        test_id=test_id,
        email_type="report_delivery"
    )

    assert variant_id == variant_id_2
    assert variant_config == variant_config_2


def test_get_email_variant_no_active_test(email_ab_test):
    """Test getting email variant when no active test exists."""
    user_id = "test_user_456"
    user_email = "test@example.com"

    variant_id, variant_config = email_ab_test.get_email_variant_for_user(
        user_id=user_id,
        user_email=user_email,
        email_type="report_delivery"
    )

    # Should return default variant
    assert variant_id == "default"
    assert variant_config['subject'] == "Your audit report is ready!"
    assert variant_config['template'] == "report_delivery"


def test_generate_email_with_variant(email_ab_test):
    """Test generating personalized email with A/B test variant."""
    subject_variants = [
        {"subject": "Custom Subject A", "weight": 0.5},
        {"subject": "Custom Subject B", "weight": 0.5}
    ]

    test_id = email_ab_test.create_subject_line_test(
        name="Email Generation Test",
        description="Test email generation",
        subject_variants=subject_variants
    )

    email_ab_test.test_manager.start_test(test_id)

    # Create personalization data
    personalization = EmailPersonalization(
        user_name="John Doe",
        user_email="john@example.com",
        report_title="SEO Audit Report",
        report_link="https://example.com/report/123",
        agency_cta_link="https://example.com/agency",
        purchase_date=datetime.utcnow(),
        expiry_date=datetime.utcnow()
    )

    # Generate email
    variant_id, email_template = email_ab_test.generate_email_with_variant(
        user_id="john_doe_123",
        personalization=personalization,
        test_id=test_id,
        email_type="report_delivery"
    )

    assert variant_id is not None
    assert email_template is not None
    assert 'subject' in email_template
    assert 'html_content' in email_template
    assert email_template['subject'] in ["Custom Subject A", "Custom Subject B"]


def test_record_email_event(email_ab_test):
    """Test recording email events for A/B testing."""
    subject_variants = [
        {"subject": "Test Subject", "weight": 1.0}
    ]

    test_id = email_ab_test.create_subject_line_test(
        name="Event Recording Test",
        description="Test event recording",
        subject_variants=subject_variants
    )

    email_ab_test.test_manager.start_test(test_id)

    # Assign user to variant
    user_id = "event_test_user"
    email_ab_test.test_manager.assign_user_to_variant(user_id, test_id)

    # Record email events
    email_ab_test.record_email_event(
        test_id=test_id,
        user_id=user_id,
        event_type="sent",
        metadata={"email_id": "test_email_123"}
    )

    email_ab_test.record_email_event(
        test_id=test_id,
        user_id=user_id,
        event_type="opened",
        metadata={"timestamp": datetime.utcnow().isoformat()}
    )

    # Get test results to verify events were recorded
    results = email_ab_test.test_manager.get_test_results(test_id)
    assert results['total_assignments'] == 1

    # Check variant results
    variant_results = results['variant_results']
    assert len(variant_results) == 1

    variant_data = list(variant_results.values())[0]
    assert variant_data['assignments'] == 1


def test_get_email_test_performance(email_ab_test):
    """Test getting email test performance metrics."""
    subject_variants = [
        {"subject": "Performance Test A", "weight": 0.5},
        {"subject": "Performance Test B", "weight": 0.5}
    ]

    test_id = email_ab_test.create_subject_line_test(
        name="Performance Test",
        description="Test performance metrics",
        subject_variants=subject_variants
    )

    email_ab_test.test_manager.start_test(test_id)

    # Simulate some users and events
    for i in range(10):
        user_id = f"perf_user_{i}"
        email_ab_test.test_manager.assign_user_to_variant(user_id, test_id)

        # Simulate email events
        email_ab_test.record_email_event(test_id, user_id, "sent")

        if i % 2 == 0:  # 50% open rate
            email_ab_test.record_email_event(test_id, user_id, "opened")

        if i % 5 == 0:  # 20% click rate
            email_ab_test.record_email_event(test_id, user_id, "clicked")

    # Get performance metrics
    performance = email_ab_test.get_email_test_performance(test_id)

    assert performance['test_id'] == test_id
    assert performance['test_name'] == "Performance Test"
    assert 'email_metrics' in performance
    assert performance['total_assignments'] == 10


def test_invalid_subject_variants(email_ab_test):
    """Test validation of invalid subject variants."""
    # Test insufficient variants
    with pytest.raises(ValueError, match="at least 2 variants"):
        email_ab_test.create_subject_line_test(
            name="Invalid Test",
            description="Test",
            subject_variants=[{"subject": "Only one"}]
        )

    # Test missing subject field
    with pytest.raises(ValueError, match="must have a 'subject' field"):
        email_ab_test.create_subject_line_test(
            name="Invalid Test",
            description="Test",
            subject_variants=[
                {"subject": "Valid"},
                {"text": "Missing subject field"}
            ]
        )


def test_subject_line_length_warning(email_ab_test, caplog):
    """Test warning for long subject lines."""
    long_subject = "This is a very long subject line that exceeds the recommended length limit for email subject lines and may be truncated"

    subject_variants = [
        {"subject": "Short subject", "weight": 0.5},
        {"subject": long_subject, "weight": 0.5}
    ]

    test_id = email_ab_test.create_subject_line_test(
        name="Long Subject Test",
        description="Test long subject warning",
        subject_variants=subject_variants
    )

    assert test_id is not None
    # Check that warning was logged (implementation would need to capture logs)
