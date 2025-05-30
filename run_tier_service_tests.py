#!/usr/bin/env python3
"""
Test runner for tier service tests using direct imports.
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import the modules
from leadfactory.config.tier_config import TierLevel
from leadfactory.services.tier_service import (
    APICallResult,
    TierService,
    get_tier_service,
)


def test_tier_service_basic():
    """Test basic tier service functionality."""
    print("🧪 Testing TierService basic functionality...")

    # Test initialization
    service = TierService(tier=1)
    assert service.tier == 1
    assert service.tier_level == TierLevel.TIER_1
    print("✅ TierService initialization works")

    # Test get_tier_service
    service2 = get_tier_service(tier=2)
    assert service2.tier == 2
    assert service2.tier_level == TierLevel.TIER_2
    print("✅ get_tier_service works")

    # Test APICallResult
    result = APICallResult(
        success=True, data={"test": "data"}, api_name="test_api", tier_limited=False
    )
    assert result.success == True
    assert result.data == {"test": "data"}
    assert result.api_name == "test_api"
    assert result.tier_limited == False
    print("✅ APICallResult works")


def test_tier_service_api_calls():
    """Test tier service API call functionality."""
    print("🧪 Testing TierService API call functionality...")

    service = TierService(tier=1)

    # Test can_call_api
    can_call_yelp = service.can_call_api("yelp")
    print(f"✅ can_call_api('yelp') for tier 1: {can_call_yelp}")

    # Test get_enabled_apis
    enabled_apis = service.get_enabled_apis()
    print(f"✅ Enabled APIs for tier 1: {enabled_apis}")

    # Test tier 2
    service2 = TierService(tier=2)
    enabled_apis_2 = service2.get_enabled_apis()
    print(f"✅ Enabled APIs for tier 2: {enabled_apis_2}")


def test_tier_service_features():
    """Test tier service feature functionality."""
    print("🧪 Testing TierService feature functionality...")

    service = TierService(tier=2)

    # Test can_use_feature with correct parameters
    can_tech_stack = service.can_use_feature("tech_stack_analysis", "enrich")
    print(
        f"✅ can_use_feature('tech_stack_analysis', 'enrich') for tier 2: {can_tech_stack}"
    )

    can_screenshot = service.can_use_feature("screenshot_capture", "enrich")
    print(
        f"✅ can_use_feature('screenshot_capture', 'enrich') for tier 2: {can_screenshot}"
    )

    can_basic_template = service.can_use_feature("basic_template", "mockup")
    print(
        f"✅ can_use_feature('basic_template', 'mockup') for tier 2: {can_basic_template}"
    )

    # Test get_enabled_features
    enabled_features_enrich = service.get_enabled_features("enrich")
    print(f"✅ Enabled features for 'enrich' stage: {enabled_features_enrich}")

    enabled_features_mockup = service.get_enabled_features("mockup")
    print(f"✅ Enabled features for 'mockup' stage: {enabled_features_mockup}")


def test_tier_configurations():
    """Test tier configuration access."""
    print("🧪 Testing tier configurations...")

    for tier in [1, 2, 3]:
        service = TierService(tier=tier)
        summary = service.get_tier_summary()
        print(f"✅ Tier {tier} summary: {summary}")


def run_all_tests():
    """Run all tier service tests."""
    print("🚀 Starting Tier Service Tests")
    print("=" * 50)

    try:
        test_tier_service_basic()
        print()

        test_tier_service_api_calls()
        print()

        test_tier_service_features()
        print()

        test_tier_configurations()
        print()

        print("=" * 50)
        print("🎉 All tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
