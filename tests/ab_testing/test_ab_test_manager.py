"""
Tests for A/B Test Manager core functionality.
"""

import contextlib
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from leadfactory.ab_testing.ab_test_manager import ABTestManager, TestStatus, TestType


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    with contextlib.suppress(FileNotFoundError):
        os.unlink(db_path)


@pytest.fixture
def test_manager(temp_db):
    """Create test manager with temporary database."""
    return ABTestManager(db_path=temp_db)


def test_create_email_test(test_manager):
    """Test creating an email A/B test."""
    variants = [
        {"subject": "Your report is ready!", "weight": 0.5},
        {"subject": "Don't miss your insights!", "weight": 0.5},
    ]

    test_id = test_manager.create_test(
        name="Email Subject Test",
        description="Test different subject lines",
        test_type=TestType.EMAIL_SUBJECT,
        variants=variants,
        target_sample_size=1000,
    )

    assert test_id is not None
    assert len(test_id) > 0

    # Verify test was created
    test_config = test_manager.get_test_config(test_id)
    assert test_config is not None
    assert test_config.name == "Email Subject Test"
    assert test_config.test_type == TestType.EMAIL_SUBJECT
    assert test_config.status == TestStatus.DRAFT
    assert len(test_config.variants) == 2


def test_create_pricing_test(test_manager):
    """Test creating a pricing A/B test."""
    variants = [{"price": 9900, "weight": 0.5}, {"price": 12900, "weight": 0.5}]

    test_id = test_manager.create_test(
        name="Pricing Test",
        description="Test different price points",
        test_type=TestType.PRICING,
        variants=variants,
        target_sample_size=500,
    )

    assert test_id is not None

    test_config = test_manager.get_test_config(test_id)
    assert test_config.name == "Pricing Test"
    assert test_config.test_type == TestType.PRICING
    assert test_config.target_sample_size == 500


def test_start_stop_test(test_manager):
    """Test starting and stopping tests."""
    variants = [
        {"subject": "Test A", "weight": 0.5},
        {"subject": "Test B", "weight": 0.5},
    ]

    test_id = test_manager.create_test(
        name="Start/Stop Test",
        description="Test lifecycle",
        test_type=TestType.EMAIL_SUBJECT,
        variants=variants,
    )

    # Start test
    success = test_manager.start_test(test_id)
    assert success is True

    test_config = test_manager.get_test_config(test_id)
    assert test_config.status == TestStatus.ACTIVE

    # Stop test
    success = test_manager.stop_test(test_id)
    assert success is True

    test_config = test_manager.get_test_config(test_id)
    assert test_config.status == TestStatus.COMPLETED


def test_user_assignment(test_manager):
    """Test user assignment to variants."""
    variants = [
        {"subject": "Variant A", "weight": 0.6},
        {"subject": "Variant B", "weight": 0.4},
    ]

    test_id = test_manager.create_test(
        name="Assignment Test",
        description="Test user assignment",
        test_type=TestType.EMAIL_SUBJECT,
        variants=variants,
    )

    test_manager.start_test(test_id)

    # Assign multiple users
    user_assignments = {}
    for i in range(100):
        user_id = f"user_{i}"
        variant_id = test_manager.assign_user_to_variant(user_id, test_id)
        user_assignments[user_id] = variant_id

    # Check consistency - same user should get same variant
    for user_id, variant_id in user_assignments.items():
        new_variant_id = test_manager.assign_user_to_variant(user_id, test_id)
        assert new_variant_id == variant_id

    # Check distribution roughly matches weights
    variant_0_count = sum(1 for v in user_assignments.values() if v == "variant_0")
    variant_1_count = sum(1 for v in user_assignments.values() if v == "variant_1")

    # Should be roughly 60/40 split (allow some variance)
    assert 50 <= variant_0_count <= 70
    assert 30 <= variant_1_count <= 50


def test_record_conversions(test_manager):
    """Test recording conversion events."""
    variants = [
        {"subject": "Variant A", "weight": 0.5},
        {"subject": "Variant B", "weight": 0.5},
    ]

    test_id = test_manager.create_test(
        name="Conversion Test",
        description="Test conversions",
        test_type=TestType.EMAIL_SUBJECT,
        variants=variants,
    )

    test_manager.start_test(test_id)

    # Assign users and record conversions
    user_id = "test_user"
    test_manager.assign_user_to_variant(user_id, test_id)

    conversion_id = test_manager.record_conversion(
        test_id=test_id,
        user_id=user_id,
        conversion_type="email_opened",
        conversion_value=0.0,
        metadata={"email_id": "test_email"},
    )

    assert conversion_id is not None
    assert len(conversion_id) > 0


def test_get_test_results(test_manager):
    """Test getting test results."""
    variants = [
        {"subject": "Variant A", "weight": 0.5},
        {"subject": "Variant B", "weight": 0.5},
    ]

    test_id = test_manager.create_test(
        name="Results Test",
        description="Test results",
        test_type=TestType.EMAIL_SUBJECT,
        variants=variants,
    )

    test_manager.start_test(test_id)

    # Assign some users and record conversions
    for i in range(20):
        user_id = f"user_{i}"
        test_manager.assign_user_to_variant(user_id, test_id)

        # Record some conversions
        if i % 5 == 0:  # 20% conversion rate
            test_manager.record_conversion(
                test_id=test_id, user_id=user_id, conversion_type="email_opened"
            )

    results = test_manager.get_test_results(test_id)

    assert results["test_id"] == test_id
    assert results["total_assignments"] == 20
    assert "variant_results" in results
    assert len(results["variant_results"]) == 2


def test_invalid_variants(test_manager):
    """Test validation of invalid variant configurations."""
    # Test insufficient variants
    with pytest.raises(ValueError, match="at least 2 variants"):
        test_manager.create_test(
            name="Invalid Test",
            description="Test",
            test_type=TestType.EMAIL_SUBJECT,
            variants=[{"subject": "Only one"}],
        )

    # Test invalid weights
    with pytest.raises(ValueError, match="must sum to 1.0"):
        test_manager.create_test(
            name="Invalid Weights",
            description="Test",
            test_type=TestType.EMAIL_SUBJECT,
            variants=[
                {"subject": "A", "weight": 0.8},
                {"subject": "B", "weight": 0.8},  # Total = 1.6
            ],
        )


def test_get_active_tests(test_manager):
    """Test getting active tests."""
    # Create multiple tests
    email_variants = [
        {"subject": "Email A", "weight": 0.5},
        {"subject": "Email B", "weight": 0.5},
    ]

    pricing_variants = [{"price": 9900, "weight": 0.5}, {"price": 12900, "weight": 0.5}]

    email_test_id = test_manager.create_test(
        name="Email Test",
        description="Email test",
        test_type=TestType.EMAIL_SUBJECT,
        variants=email_variants,
    )

    test_manager.create_test(
        name="Pricing Test",
        description="Pricing test",
        test_type=TestType.PRICING,
        variants=pricing_variants,
    )

    # Start email test only
    test_manager.start_test(email_test_id)

    # Get all active tests
    active_tests = test_manager.get_active_tests()
    assert len(active_tests) == 1
    assert active_tests[0].id == email_test_id

    # Get active email tests
    email_tests = test_manager.get_active_tests(TestType.EMAIL_SUBJECT)
    assert len(email_tests) == 1
    assert email_tests[0].test_type == TestType.EMAIL_SUBJECT

    # Get active pricing tests (should be empty)
    pricing_tests = test_manager.get_active_tests(TestType.PRICING)
    assert len(pricing_tests) == 0
