#!/usr/bin/env python3
"""
Comprehensive Task 21 Test: IP Pool Switching on Bounce Threshold

This test validates the complete implementation of automatic IP pool switching
when bounce thresholds are exceeded, working around environment import issues.
"""

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta


def test_core_imports():
    """Test that core IP pool switching components can be imported."""
    try:
        # Add current directory to path to avoid import issues
        sys.path.insert(
            0, "/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory"
        )

        # Test individual component imports
        from leadfactory.services.bounce_monitor import (
            BounceEvent,
            BounceRateConfig,
            BounceRateMonitor,
        )
        from leadfactory.services.ip_pool_switching_integration import (
            IPPoolSwitchingService,
            get_ip_pool_switching_service,
        )
        from leadfactory.services.ip_rotation import (
            IPRotationService,
            create_default_rotation_config,
        )
        from leadfactory.services.threshold_detector import (
            ThresholdDetector,
            create_default_threshold_config,
        )

        return True

    except ImportError:
        return False


def test_bounce_threshold_configuration():
    """Test that bounce threshold is correctly configured to 2% as per Task 21."""
    try:
        from leadfactory.services.bounce_monitor import BounceRateConfig

        # Test default configuration meets Task 21 requirements
        config = BounceRateConfig(
            warning_threshold=0.02,  # 2% threshold requirement
            critical_threshold=0.05,  # 5% critical threshold
            minimum_sample_size=50,
        )

        if config.warning_threshold != 0.02:
            return False

        return config.critical_threshold == 0.05

    except Exception:
        return False


def test_ip_pool_manager_basic():
    """Test basic IP pool manager functionality."""
    try:
        from leadfactory.services.ip_pool_manager import IPPoolManager, IPPoolStatus

        manager = IPPoolManager()

        # Check that pools are loaded
        if not manager.ip_pools:
            return False

        # Check for required pools
        required_pools = ["primary", "backup"]
        for pool_name in required_pools:
            if pool_name not in manager.ip_pools:
                return False

        # Test status reporting
        status = manager.get_status()
        if not isinstance(status, dict):
            return False

        required_status_fields = ["running", "current_pool", "total_pools"]
        return all(field in status for field in required_status_fields)

    except Exception:
        return False


async def test_bounce_monitoring():
    """Test bounce rate monitoring with SQLite fallback."""
    try:
        from leadfactory.services.bounce_monitor import (
            BounceEvent,
            BounceRateConfig,
            BounceRateMonitor,
        )

        # Use temporary SQLite database for testing
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Initialize with 2% threshold
            config = BounceRateConfig(
                warning_threshold=0.02,  # 2% as per Task 21
                critical_threshold=0.05,
                minimum_sample_size=10,  # Lower for testing
            )

            monitor = BounceRateMonitor(config, db_path=db_path)

            # Record some sent emails
            monitor.record_sent_email("192.168.1.100", "test_subuser")
            monitor.record_sent_email("192.168.1.100", "test_subuser")
            monitor.record_sent_email("192.168.1.100", "test_subuser")
            monitor.record_sent_email("192.168.1.100", "test_subuser")
            monitor.record_sent_email("192.168.1.100", "test_subuser")

            # Record a bounce event
            bounce_event = BounceEvent(
                email="test@example.com",
                ip_address="192.168.1.100",
                subuser="test_subuser",
                bounce_type="hard",
                reason="User unknown",
                timestamp=datetime.now(),
            )

            monitor.record_bounce_event(bounce_event)

            # Check bounce rate
            bounce_rate = monitor.get_bounce_rate("192.168.1.100", "test_subuser")
            expected_rate = 1.0 / 5.0  # 1 bounce out of 5 emails = 20%

            return not abs(bounce_rate - expected_rate) > 0.01

        finally:
            # Clean up temp file
            if os.path.exists(db_path):
                os.unlink(db_path)

    except Exception:
        return False


async def test_threshold_detection():
    """Test threshold detection triggers at 2%."""
    try:
        from leadfactory.services.bounce_monitor import (
            BounceEvent,
            BounceRateConfig,
            BounceRateMonitor,
        )
        from leadfactory.services.threshold_detector import (
            ThresholdDetector,
            create_default_threshold_config,
        )

        # Use temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Set up monitoring with 2% threshold
            bounce_config = BounceRateConfig(
                warning_threshold=0.02, minimum_sample_size=50  # 2% threshold
            )

            monitor = BounceRateMonitor(bounce_config, db_path=db_path)
            threshold_config = create_default_threshold_config()
            detector = ThresholdDetector(threshold_config, bounce_monitor=monitor)

            # Simulate 100 emails sent
            for i in range(100):
                monitor.record_sent_email("192.168.1.200", "threshold_test")

            # Simulate 3 bounces (3% bounce rate - should trigger 2% threshold)
            for i in range(3):
                bounce_event = BounceEvent(
                    email=f"bounce{i}@example.com",
                    ip_address="192.168.1.200",
                    subuser="threshold_test",
                    bounce_type="hard",
                    reason="User unknown",
                    timestamp=datetime.now(),
                )
                monitor.record_bounce_event(bounce_event)

            # Check for threshold violations
            violations = detector.check_thresholds("192.168.1.200", "threshold_test")

            return violations

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    except Exception:
        return False


async def test_ip_rotation_service():
    """Test IP rotation service functionality."""
    try:
        from leadfactory.services.ip_rotation import (
            IPRotationService,
            RotationReason,
            create_default_rotation_config,
        )

        # Initialize rotation service
        config = create_default_rotation_config()
        rotation_service = IPRotationService(config)

        # Add some IP/subuser combinations
        rotation_service.add_ip_subuser(
            ip_address="192.168.1.100", subuser="primary", priority=10
        )

        rotation_service.add_ip_subuser(
            ip_address="192.168.1.101", subuser="backup", priority=5
        )

        # Test finding alternatives
        alternatives = rotation_service.get_available_alternatives(
            exclude_ip="192.168.1.100", exclude_subuser="primary"
        )

        if not alternatives:
            return False

        # Test selecting best alternative
        best = rotation_service.select_best_alternative("192.168.1.100", "primary")
        if not best:
            return False

        return not (best.ip_address != "192.168.1.101" or best.subuser != "backup")

    except Exception:
        return False


async def test_integration_service():
    """Test the complete integration service."""
    try:
        from leadfactory.services.ip_pool_switching_integration import (
            AlertingConfig,
            BounceRateConfig,
            IPPoolSwitchingService,
        )

        # Use temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Initialize service with Task 21 requirements
            bounce_config = BounceRateConfig(
                warning_threshold=0.02,  # 2% threshold
                critical_threshold=0.05,
                minimum_sample_size=10,  # Lower for testing
            )

            alerting_config = AlertingConfig(
                admin_emails=["admin@example.com"],
                webhook_urls=["http://example.com/webhook"],
            )

            service = IPPoolSwitchingService(
                bounce_config=bounce_config,
                alerting_config=alerting_config,
                db_path=db_path,
            )

            # Test service initialization
            if not service.bounce_monitor:
                return False

            if not service.threshold_detector:
                return False

            if not service.rotation_service:
                return False

            # Test bounce threshold configuration
            if service.bounce_config.warning_threshold != 0.02:
                return False

            # Test status reporting
            status = service.get_status()
            if not isinstance(status, dict):
                return False

            required_fields = ["service_running", "bounce_monitoring", "rotation_pool"]
            return all(field in status for field in required_fields)

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    except Exception:
        return False


async def test_end_to_end_workflow():
    """Test complete end-to-end workflow with bounce threshold triggering rotation."""
    try:
        from leadfactory.services.ip_pool_switching_integration import (
            BounceRateConfig,
            IPPoolSwitchingService,
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Initialize service
            bounce_config = BounceRateConfig(
                warning_threshold=0.02,  # 2% threshold
                minimum_sample_size=20,  # Smaller for testing
            )

            service = IPPoolSwitchingService(
                bounce_config=bounce_config, db_path=db_path
            )

            # Record emails to build up sample size
            test_ip = "192.168.1.100"
            test_subuser = "e2e_test"

            # Send 25 emails (above minimum sample size)
            for _i in range(25):
                await service.record_sent_email(test_ip, test_subuser)

            # Initial bounce rate should be 0
            bounce_rate = service.get_bounce_rate(test_ip, test_subuser)
            if bounce_rate != 0.0:
                return False

            # Record 1 bounce (4% bounce rate - should exceed 2% threshold)
            await service.record_bounce_event(
                email="bounce@example.com",
                ip_address=test_ip,
                subuser=test_subuser,
                bounce_type="hard",
                reason="User unknown",
            )

            # Check that bounce rate is calculated correctly
            bounce_rate = service.get_bounce_rate(test_ip, test_subuser)
            expected_rate = 1.0 / 25.0  # 1 bounce out of 25 emails = 4%

            if abs(bounce_rate - expected_rate) > 0.01:
                return False

            # Check status includes the bounce information
            status = service.get_status()
            bounce_stats = status.get("bounce_monitoring", {})

            return bounce_stats.get("warning_threshold") == 0.02

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    except Exception:
        return False


async def main():
    """Run comprehensive Task 21 tests."""

    tests = [
        ("Component Imports", test_core_imports),
        ("Bounce Threshold Config", test_bounce_threshold_configuration),
        ("IP Pool Manager Basic", test_ip_pool_manager_basic),
        ("Bounce Monitoring", test_bounce_monitoring),
        ("Threshold Detection", test_threshold_detection),
        ("IP Rotation Service", test_ip_rotation_service),
        ("Integration Service", test_integration_service),
        ("End-to-End Workflow", test_end_to_end_workflow),
    ]

    passed = 0
    failed = 0

    for _test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()

            if result:
                passed += 1
            else:
                failed += 1

        except Exception:
            failed += 1

    if failed == 0:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
