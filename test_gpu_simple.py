#!/usr/bin/env python3
"""
Simple test script for GPU Auto-Scaling System.
Tests individual modules without complex imports.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_gpu_enums():
    """Test GPU instance types and enums."""
    try:
        # Import just the enum without the full module
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gpu_manager", "leadfactory/services/gpu_manager.py"
        )
        gpu_module = importlib.util.module_from_spec(spec)

        # Mock dependencies
        sys.modules["leadfactory.utils.metrics"] = type(
            "MockModule",
            (),
            {
                "GPU_INSTANCES_ACTIVE": None,
                "GPU_QUEUE_SIZE": None,
                "GPU_PROVISIONING_TIME": None,
                "GPU_COST_HOURLY": None,
                "GPU_UTILIZATION": None,
                "GPU_SCALING_EVENTS": None,
                "record_metric": lambda *args, **kwargs: None,
            },
        )()

        sys.modules["leadfactory.services.gpu_alerting"] = type(
            "MockModule", (), {"check_all_gpu_alerts": lambda *args: []}
        )()

        sys.modules["leadfactory.services.gpu_security"] = type(
            "MockModule",
            (),
            {
                "credential_manager": type(
                    "MockCredManager",
                    (),
                    {"get_credential": lambda self, p, t: "mock-token"},
                )(),
                "network_security": type(
                    "MockNetSec", (), {"load_ssh_keys": lambda self: ["mock-key"]}
                )(),
                "audit_logger": type(
                    "MockAudit", (), {"log_event": lambda self, *args, **kwargs: None}
                )(),
                "rate_limiter": type(
                    "MockRate", (), {"check_rate_limit": lambda self, *args: True}
                )(),
            },
        )()

        spec.loader.exec_module(gpu_module)

        # Test enum values
        assert gpu_module.GPUInstanceType.HETZNER_GTX1080.value == "hetzner.gtx1080"
        assert gpu_module.GPUInstanceType.HETZNER_RTX3080.value == "hetzner.rtx3080"
        assert gpu_module.GPUInstanceType.AWS_G4DN_XLARGE.value == "g4dn.xlarge"

        return True

    except Exception:
        return False


def test_hetzner_client():
    """Test Hetzner API client class."""
    try:
        # Mock requests module
        import types

        requests_mock = types.ModuleType("requests")

        def mock_post(*args, **kwargs):
            response = types.SimpleNamespace()
            response.json = lambda: {"server": {"id": 123, "name": "test"}}
            response.raise_for_status = lambda: None
            return response

        def mock_get(*args, **kwargs):
            response = types.SimpleNamespace()
            response.json = lambda: {"server": {"id": 123, "status": "running"}}
            response.raise_for_status = lambda: None
            return response

        def mock_delete(*args, **kwargs):
            response = types.SimpleNamespace()
            response.json = lambda: {}
            response.raise_for_status = lambda: None
            return response

        requests_mock.post = mock_post
        requests_mock.get = mock_get
        requests_mock.delete = mock_delete

        sys.modules["requests"] = requests_mock

        # Import and test HetznerAPIClient
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gpu_manager", "leadfactory/services/gpu_manager.py"
        )
        gpu_module = importlib.util.module_from_spec(spec)

        # Mock other dependencies
        sys.modules["leadfactory.utils.metrics"] = type("MockModule", (), {})()
        sys.modules["leadfactory.services.gpu_alerting"] = type("MockModule", (), {})()
        sys.modules["leadfactory.services.gpu_security"] = type("MockModule", (), {})()

        spec.loader.exec_module(gpu_module)

        # Test HetznerAPIClient
        client = gpu_module.HetznerAPIClient("test-token")
        assert client.api_token == "test-token"
        assert "Bearer test-token" in client.headers["Authorization"]

        # Test API calls
        result = client.create_server("test", "cx21", "ubuntu-20.04")
        assert result["server"]["id"] == 123

        result = client.get_server("123")
        assert result["server"]["status"] == "running"

        client.delete_server("123")  # Should not throw

        return True

    except Exception:
        return False


def test_data_classes():
    """Test GPU data classes."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gpu_manager", "leadfactory/services/gpu_manager.py"
        )
        gpu_module = importlib.util.module_from_spec(spec)

        # Mock dependencies
        sys.modules["leadfactory.utils.metrics"] = type("MockModule", (), {})()
        sys.modules["leadfactory.services.gpu_alerting"] = type("MockModule", (), {})()
        sys.modules["leadfactory.services.gpu_security"] = type("MockModule", (), {})()

        spec.loader.exec_module(gpu_module)

        # Test QueueMetrics
        metrics = gpu_module.QueueMetrics(
            total_tasks=100,
            pending_tasks=50,
            processing_tasks=25,
            average_processing_time=180.0,
            estimated_completion_time=900.0,
            queue_growth_rate=2.5,
        )
        assert metrics.total_tasks == 100
        assert metrics.pending_tasks == 50

        # Test GPUResourceConfig
        config = gpu_module.GPUResourceConfig(
            instance_type=gpu_module.GPUInstanceType.HETZNER_GTX1080,
            max_concurrent_tasks=8,
            cost_per_hour=0.35,
            memory_gb=32,
            vram_gb=8,
            cuda_cores=2560,
        )
        assert config.cost_per_hour == 0.35
        assert config.max_concurrent_tasks == 8

        # Test GPUInstance
        from datetime import datetime

        instance = gpu_module.GPUInstance(
            instance_id="test-123",
            instance_type=gpu_module.GPUInstanceType.HETZNER_GTX1080,
            status="running",
            start_time=datetime.now(),
        )
        assert instance.instance_id == "test-123"
        assert instance.status == "running"

        return True

    except Exception:
        return False


def test_sql_migration():
    """Test SQL migration file."""
    try:
        with open("db/migrations/add_personalization_queue.sql") as f:
            sql_content = f.read()

        # Basic SQL validation
        assert "CREATE TABLE" in sql_content
        assert "personalization_queue" in sql_content
        assert "gpu_required BOOLEAN" in sql_content
        assert "task_type TEXT NOT NULL" in sql_content
        assert "CREATE INDEX" in sql_content

        return True

    except Exception:
        return False


def test_config_files():
    """Test configuration files."""
    try:
        import yaml

        with open("etc/gpu_config.yml") as f:
            config = yaml.safe_load(f)

        # Validate configuration structure
        assert "budget" in config
        assert "queue_thresholds" in config
        assert "instances" in config
        assert "hetzner" in config

        # Check threshold values
        assert config["queue_thresholds"]["scale_up_pending"] == 2000
        assert config["budget"]["daily_limit"] == 500.0

        # Check Hetzner instances are configured
        assert "hetzner_gtx1080" in config["instances"]
        assert "hetzner_rtx3080" in config["instances"]
        assert "hetzner_rtx4090" in config["instances"]

        return True

    except Exception:
        return False


def main():
    """Run all simple tests."""

    tests = [
        test_gpu_enums,
        test_hetzner_client,
        test_data_classes,
        test_sql_migration,
        test_config_files,
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
