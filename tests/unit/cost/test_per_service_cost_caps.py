"""
Unit tests for per-service cost caps system.
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.cost.per_service_cost_caps import (
    PerServiceCostCaps,
    ServiceCostCap,
    ServiceCostStatus,
    ServiceStatus,
    can_execute_service_operation,
    get_cost_caps_summary,
    get_service_cost_status,
)


class TestServiceCostCap:
    """Test the ServiceCostCap dataclass."""

    def test_service_cost_cap_creation(self):
        """Test creating a service cost cap."""
        cap = ServiceCostCap(
            service="openai",
            daily_limit=20.0,
            warning_threshold=0.8,
            critical_threshold=0.9,
        )

        assert cap.service == "openai"
        assert cap.daily_limit == 20.0
        assert cap.warning_threshold == 0.8
        assert cap.critical_threshold == 0.9
        assert cap.enabled is True


class TestServiceCostStatus:
    """Test the ServiceCostStatus dataclass."""

    def test_service_cost_status_creation(self):
        """Test creating a service cost status."""
        status = ServiceCostStatus(
            service="openai",
            daily_spent=10.0,
            daily_limit=20.0,
            remaining=10.0,
            utilization_percent=50.0,
            status=ServiceStatus.WARNING,
            last_updated=datetime.now(),
        )

        assert status.service == "openai"
        assert status.daily_spent == 10.0
        assert status.daily_limit == 20.0
        assert status.remaining == 10.0
        assert status.utilization_percent == 50.0
        assert status.status == ServiceStatus.WARNING


class TestPerServiceCostCaps:
    """Test the PerServiceCostCaps class."""

    @pytest.fixture
    def mock_cost_tracker(self):
        """Mock cost tracker for testing."""
        mock_tracker = MagicMock()
        mock_tracker.get_daily_cost.return_value = 0.0
        mock_tracker.get_daily_cost_breakdown.return_value = {}
        return mock_tracker

    @pytest.fixture
    def cost_caps_service(self, mock_cost_tracker):
        """Create cost caps service with mocked dependencies."""
        with patch.dict(os.environ, {
            "OPENAI_DAILY_CAP": "20.0",
            "SEMRUSH_DAILY_CAP": "5.0",
            "ENFORCE_SERVICE_COST_CAPS": "true",
        }):
            with patch("leadfactory.cost.per_service_cost_caps.cost_tracker", mock_cost_tracker):
                service = PerServiceCostCaps()
                return service

    def test_initialization(self, cost_caps_service):
        """Test service initialization."""
        assert len(cost_caps_service.service_caps) >= 5  # At least 5 default services
        assert "openai" in cost_caps_service.service_caps
        assert "semrush" in cost_caps_service.service_caps
        assert cost_caps_service.enforcement_enabled is True

    def test_load_service_caps_from_environment(self):
        """Test loading service caps from environment variables."""
        with patch.dict(os.environ, {
            "OPENAI_DAILY_CAP": "25.0",
            "OPENAI_WARNING_THRESHOLD": "0.7",
            "OPENAI_CRITICAL_THRESHOLD": "0.85",
        }):
            service = PerServiceCostCaps()

            openai_cap = service.service_caps["openai"]
            assert openai_cap.daily_limit == 25.0
            assert openai_cap.warning_threshold == 0.7
            assert openai_cap.critical_threshold == 0.85

    def test_get_service_status_available(self, cost_caps_service, mock_cost_tracker):
        """Test getting service status when service is available."""
        mock_cost_tracker.get_daily_cost.return_value = 5.0

        status = cost_caps_service.get_service_status("openai")

        assert status.service == "openai"
        assert status.daily_spent == 5.0
        assert status.daily_limit == 20.0
        assert status.remaining == 15.0
        assert status.utilization_percent == 25.0
        assert status.status == ServiceStatus.AVAILABLE

    def test_get_service_status_warning(self, cost_caps_service, mock_cost_tracker):
        """Test getting service status when service is in warning state."""
        mock_cost_tracker.get_daily_cost.return_value = 16.0  # 80% of 20.0

        status = cost_caps_service.get_service_status("openai")

        assert status.utilization_percent == 80.0
        assert status.status == ServiceStatus.WARNING

    def test_get_service_status_critical(self, cost_caps_service, mock_cost_tracker):
        """Test getting service status when service is in critical state."""
        mock_cost_tracker.get_daily_cost.return_value = 18.0  # 90% of 20.0

        status = cost_caps_service.get_service_status("openai")

        assert status.utilization_percent == 90.0
        assert status.status == ServiceStatus.CRITICAL

    def test_get_service_status_capped(self, cost_caps_service, mock_cost_tracker):
        """Test getting service status when service is capped."""
        mock_cost_tracker.get_daily_cost.return_value = 20.0  # 100% of 20.0

        status = cost_caps_service.get_service_status("openai")

        assert status.utilization_percent == 100.0
        assert status.status == ServiceStatus.CAPPED
        assert status.remaining == 0.0

    def test_get_service_status_unknown_service(self, cost_caps_service):
        """Test getting status for unknown service."""
        status = cost_caps_service.get_service_status("unknown_service")

        assert status.service == "unknown_service"
        assert status.daily_limit == 0.0
        assert status.status == ServiceStatus.AVAILABLE

    def test_can_execute_operation_allowed(self, cost_caps_service, mock_cost_tracker):
        """Test operation execution when allowed."""
        mock_cost_tracker.get_daily_cost.return_value = 10.0

        can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 5.0)

        assert can_execute is True
        assert "within service cap" in reason
        assert status.service == "openai"

    def test_can_execute_operation_would_exceed_cap(self, cost_caps_service, mock_cost_tracker):
        """Test operation execution when it would exceed cap."""
        mock_cost_tracker.get_daily_cost.return_value = 18.0

        can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 5.0)

        assert can_execute is False
        assert "would exceed" in reason
        assert "$23.00 > $20.00" in reason

    def test_can_execute_operation_already_capped(self, cost_caps_service, mock_cost_tracker):
        """Test operation execution when service is already capped."""
        mock_cost_tracker.get_daily_cost.return_value = 20.0

        can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 1.0)

        assert can_execute is False
        assert "exceeded daily cap" in reason
        assert status.status == ServiceStatus.CAPPED

    def test_can_execute_operation_enforcement_disabled(self, mock_cost_tracker):
        """Test operation execution when enforcement is disabled."""
        with patch.dict(os.environ, {"ENFORCE_SERVICE_COST_CAPS": "false"}):
            with patch("leadfactory.cost.per_service_cost_caps.cost_tracker", mock_cost_tracker):
                service = PerServiceCostCaps()
                mock_cost_tracker.get_daily_cost.return_value = 25.0  # Over limit

                can_execute, reason, status = service.can_execute_operation("openai", 10.0)

                assert can_execute is True
                assert "enforcement disabled" in reason

    def test_get_all_service_statuses(self, cost_caps_service, mock_cost_tracker):
        """Test getting all service statuses."""
        mock_cost_tracker.get_daily_cost.return_value = 10.0

        statuses = cost_caps_service.get_all_service_statuses()

        assert len(statuses) >= 5
        assert "openai" in statuses
        assert "semrush" in statuses
        assert all(isinstance(status, ServiceCostStatus) for status in statuses.values())

    def test_get_capped_services(self, cost_caps_service, mock_cost_tracker):
        """Test getting list of capped services."""
        def mock_daily_cost(service):
            if service == "openai":
                return 20.0  # Capped
            elif service == "semrush":
                return 5.0   # Capped
            else:
                return 1.0   # Not capped

        mock_cost_tracker.get_daily_cost.side_effect = mock_daily_cost

        capped_services = cost_caps_service.get_capped_services()

        assert "openai" in capped_services
        assert "semrush" in capped_services

    def test_get_warning_services(self, cost_caps_service, mock_cost_tracker):
        """Test getting list of services in warning state."""
        def mock_daily_cost(service):
            if service == "openai":
                return 16.0  # 80% - warning
            elif service == "semrush":
                return 4.5   # 90% - critical
            else:
                return 1.0   # Normal

        mock_cost_tracker.get_daily_cost.side_effect = mock_daily_cost

        warning_services = cost_caps_service.get_warning_services()

        assert "openai" in warning_services
        assert "semrush" in warning_services

    def test_update_service_cap_existing(self, cost_caps_service):
        """Test updating an existing service cap."""
        result = cost_caps_service.update_service_cap(
            "openai",
            daily_limit=30.0,
            warning_threshold=0.75,
            critical_threshold=0.85,
        )

        assert result is True
        cap = cost_caps_service.service_caps["openai"]
        assert cap.daily_limit == 30.0
        assert cap.warning_threshold == 0.75
        assert cap.critical_threshold == 0.85

    def test_update_service_cap_new_service(self, cost_caps_service):
        """Test updating cap for a new service."""
        result = cost_caps_service.update_service_cap("new_service", daily_limit=10.0)

        assert result is True
        assert "new_service" in cost_caps_service.service_caps
        cap = cost_caps_service.service_caps["new_service"]
        assert cap.daily_limit == 10.0
        assert cap.enabled is True

    def test_disable_enable_service_cap(self, cost_caps_service):
        """Test disabling and enabling service caps."""
        # Disable
        result = cost_caps_service.disable_service_cap("openai")
        assert result is True
        assert cost_caps_service.service_caps["openai"].enabled is False

        # Enable
        result = cost_caps_service.enable_service_cap("openai")
        assert result is True
        assert cost_caps_service.service_caps["openai"].enabled is True

    def test_get_cost_cap_report(self, cost_caps_service, mock_cost_tracker):
        """Test generating cost cap report."""
        mock_cost_tracker.get_daily_cost.return_value = 10.0

        report = cost_caps_service.get_cost_cap_report()

        assert "timestamp" in report
        assert "enforcement_enabled" in report
        assert "summary" in report
        assert "services" in report
        assert "capped_services" in report
        assert "warning_services" in report

        # Check summary structure
        summary = report["summary"]
        assert "total_daily_limit" in summary
        assert "total_daily_spent" in summary
        assert "services_total" in summary

    def test_estimate_remaining_capacity(self, cost_caps_service, mock_cost_tracker):
        """Test estimating remaining capacity for a service."""
        mock_cost_tracker.get_daily_cost.return_value = 10.0
        mock_cost_tracker.get_daily_cost_breakdown.return_value = {
            "openai": {"gpt-4": 8.0, "gpt-3.5": 2.0}
        }

        capacity = cost_caps_service.estimate_remaining_capacity("openai")

        assert capacity["service"] == "openai"
        assert capacity["remaining_budget"] == 10.0  # 20 - 10
        assert "estimated_operations" in capacity
        assert "time_until_cap" in capacity
        assert "current_burn_rate" in capacity


class TestConvenienceFunctions:
    """Test convenience functions."""

    @patch("leadfactory.cost.per_service_cost_caps.per_service_cost_caps")
    def test_can_execute_service_operation(self, mock_caps):
        """Test convenience function for checking service operation."""
        mock_caps.can_execute_operation.return_value = (True, "OK", None)

        can_execute, reason = can_execute_service_operation("openai", 5.0)

        assert can_execute is True
        assert reason == "OK"
        mock_caps.can_execute_operation.assert_called_once_with("openai", 5.0)

    @patch("leadfactory.cost.per_service_cost_caps.per_service_cost_caps")
    def test_get_service_cost_status(self, mock_caps):
        """Test convenience function for getting service status."""
        mock_status = MagicMock()
        mock_caps.get_service_status.return_value = mock_status

        status = get_service_cost_status("openai")

        assert status == mock_status
        mock_caps.get_service_status.assert_called_once_with("openai")

    @patch("leadfactory.cost.per_service_cost_caps.per_service_cost_caps")
    def test_get_cost_caps_summary(self, mock_caps):
        """Test convenience function for getting cost caps summary."""
        mock_report = {"summary": "test"}
        mock_caps.get_cost_cap_report.return_value = mock_report

        summary = get_cost_caps_summary()

        assert summary == mock_report
        mock_caps.get_cost_cap_report.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
