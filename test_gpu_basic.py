#!/usr/bin/env python3
"""
Basic test script for GPU Auto-Scaling System.
Tests core functionality without external dependencies.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_gpu_manager_imports():
    """Test that GPU manager can be imported."""
    try:
        # Test individual components
        from leadfactory.services.gpu_manager import (
            GPUInstance,
            GPUInstanceType,
            GPUResourceConfig,
            HetznerAPIClient,
            QueueMetrics,
        )

        return True
    except ImportError:
        return False


def test_gpu_security_imports():
    """Test that GPU security can be imported."""
    try:
        from leadfactory.services.gpu_security import (
            CredentialManager,
            NetworkSecurityManager,
            SecurityConfig,
        )

        return True
    except ImportError:
        return False


def test_gpu_alerting_imports():
    """Test that GPU alerting can be imported."""
    try:
        from leadfactory.services.gpu_alerting import GPUAlertManager

        return True
    except ImportError:
        return False


def test_basic_functionality():
    """Test basic GPU manager functionality."""
    try:
        from leadfactory.services.gpu_manager import GPUInstanceType, GPUResourceConfig

        # Test enum
        assert GPUInstanceType.HETZNER_GTX1080.value == "hetzner.gtx1080"

        # Test resource config
        config = GPUResourceConfig(
            instance_type=GPUInstanceType.HETZNER_GTX1080,
            max_concurrent_tasks=8,
            cost_per_hour=0.35,
            memory_gb=32,
            vram_gb=8,
            cuda_cores=2560,
        )
        assert config.cost_per_hour == 0.35

        return True
    except Exception:
        return False


def test_security_functionality():
    """Test basic security functionality."""
    try:
        from leadfactory.services.gpu_security import CredentialManager

        # Test credential manager
        cred_manager = CredentialManager()
        success = cred_manager.store_credential(
            "test", "token", "test123", encrypted=False
        )
        assert success

        retrieved = cred_manager.get_credential("test", "token")
        assert retrieved == "test123"

        return True
    except Exception:
        return False


def test_alerting_functionality():
    """Test basic alerting functionality."""
    try:
        from leadfactory.services.gpu_alerting import GPUAlertManager

        # Test alert manager
        alert_manager = GPUAlertManager()

        # Test budget alerts
        alerts = alert_manager.check_budget_alerts(90.0, 100.0)  # 90% of budget
        assert len(alerts) > 0
        assert alerts[0]["type"] == "budget_warning"

        return True
    except Exception:
        return False


def main():
    """Run all basic tests."""

    tests = [
        test_gpu_manager_imports,
        test_gpu_security_imports,
        test_gpu_alerting_imports,
        test_basic_functionality,
        test_security_functionality,
        test_alerting_functionality,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
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
    sys.exit(main())
