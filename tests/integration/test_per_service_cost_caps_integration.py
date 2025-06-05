"""
Integration tests for per-service cost caps with cost tracking system.
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

from leadfactory.cost.cost_tracking import CostTracker
from leadfactory.cost.per_service_cost_caps import PerServiceCostCaps, ServiceStatus
from leadfactory.cost.service_cost_decorators import (
    ServiceCostCapExceeded,
    enforce_service_cost_cap,
)


class TestPerServiceCostCapsIntegration:
    """Integration tests for per-service cost caps with real cost tracking."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def cost_tracker(self, temp_db):
        """Create cost tracker with temporary database."""
        return CostTracker(db_path=temp_db)
    
    @pytest.fixture
    def cost_caps_service(self, cost_tracker):
        """Create cost caps service with real cost tracker."""
        with patch.dict(os.environ, {
            "OPENAI_DAILY_CAP": "10.0",
            "SEMRUSH_DAILY_CAP": "5.0",
            "SCREENSHOT_DAILY_CAP": "2.0",
            "ENFORCE_SERVICE_COST_CAPS": "true",
        }):
            with patch("leadfactory.cost.per_service_cost_caps.cost_tracker", cost_tracker):
                service = PerServiceCostCaps()
                return service
    
    def test_service_cap_enforcement_with_real_cost_tracking(self, cost_tracker, cost_caps_service):
        """Test that service caps work with real cost tracking."""
        # Initially, all services should be available
        status = cost_caps_service.get_service_status("openai")
        assert status.status == ServiceStatus.AVAILABLE
        assert status.daily_spent == 0.0
        assert status.remaining == 10.0
        
        # Add some costs to OpenAI service
        cost_tracker.add_cost(3.0, "openai", "gpt-4")
        cost_tracker.add_cost(2.0, "openai", "gpt-3.5")
        
        # Check status after adding costs
        status = cost_caps_service.get_service_status("openai")
        assert status.daily_spent == 5.0
        assert status.remaining == 5.0
        assert status.utilization_percent == 50.0
        assert status.status == ServiceStatus.AVAILABLE
        
        # Add more costs to push into warning territory (80% of 10.0 = 8.0)
        cost_tracker.add_cost(3.5, "openai", "gpt-4")
        
        status = cost_caps_service.get_service_status("openai")
        assert status.daily_spent == 8.5
        assert status.utilization_percent == 85.0
        assert status.status == ServiceStatus.WARNING
        
        # Add costs to push over the limit
        cost_tracker.add_cost(2.0, "openai", "gpt-4")
        
        status = cost_caps_service.get_service_status("openai")
        assert status.daily_spent == 10.5
        assert status.utilization_percent > 100.0
        assert status.status == ServiceStatus.CAPPED
        assert status.remaining == 0.0
    
    def test_can_execute_operation_with_real_costs(self, cost_tracker, cost_caps_service):
        """Test operation execution checks with real cost data."""
        # Initially should be able to execute
        can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 5.0)
        assert can_execute is True
        assert "within service cap" in reason
        
        # Add costs close to limit
        cost_tracker.add_cost(8.0, "openai", "gpt-4")
        
        # Should still be able to execute small operation
        can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 1.0)
        assert can_execute is True
        
        # Should not be able to execute large operation
        can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 3.0)
        assert can_execute is False
        assert "would exceed" in reason
        
        # Add costs to reach limit
        cost_tracker.add_cost(2.0, "openai", "gpt-4")
        
        # Should not be able to execute any operation
        can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 0.1)
        assert can_execute is False
        assert "exceeded daily cap" in reason
    
    def test_decorator_integration_with_cost_tracking(self, cost_tracker):
        """Test that decorators work with real cost tracking."""
        with patch.dict(os.environ, {
            "OPENAI_DAILY_CAP": "1.0",  # Very low cap for testing
            "ENFORCE_SERVICE_COST_CAPS": "true",
        }):
            with patch("leadfactory.cost.service_cost_decorators.cost_tracker", cost_tracker):
                with patch("leadfactory.cost.per_service_cost_caps.cost_tracker", cost_tracker):
                    with patch("leadfactory.cost.service_cost_decorators.per_service_cost_caps") as mock_caps:
                        # Create a real cost caps service that uses the real cost tracker
                        real_caps = PerServiceCostCaps()
                        real_caps.cost_tracker = cost_tracker
                        mock_caps.can_execute_operation.side_effect = real_caps.can_execute_operation
                        
                        @enforce_service_cost_cap("openai", "gpt-4", estimated_cost=0.5)
                        def call_openai():
                            return {"result": "success", "cost": 0.5}
                        
                        # First call should succeed
                        result = call_openai()
                        assert result["result"] == "success"
                        
                        # Check that cost was tracked
                        daily_cost = cost_tracker.get_daily_cost("openai")
                        assert daily_cost == 0.5
                        
                        # Second call should succeed (total: 1.0)
                        result = call_openai()
                        assert result["result"] == "success"
                        
                        daily_cost = cost_tracker.get_daily_cost("openai")
                        assert daily_cost == 1.0
                        
                        # Third call should fail due to cap
                        with pytest.raises(ServiceCostCapExceeded):
                            call_openai()
    
    def test_multiple_services_independent_caps(self, cost_tracker, cost_caps_service):
        """Test that different services have independent caps."""
        # Add costs to OpenAI service
        cost_tracker.add_cost(9.0, "openai", "gpt-4")
        
        # Add costs to Semrush service
        cost_tracker.add_cost(2.0, "semrush", "domain-overview")
        
        # Check OpenAI status (near cap)
        openai_status = cost_caps_service.get_service_status("openai")
        assert openai_status.daily_spent == 9.0
        assert openai_status.status == ServiceStatus.CRITICAL  # 90% of 10.0
        
        # Check Semrush status (under cap)
        semrush_status = cost_caps_service.get_service_status("semrush")
        assert semrush_status.daily_spent == 2.0
        assert semrush_status.status == ServiceStatus.AVAILABLE  # 40% of 5.0
        
        # OpenAI should not be able to execute large operations
        can_execute, _, _ = cost_caps_service.can_execute_operation("openai", 2.0)
        assert can_execute is False
        
        # Semrush should still be able to execute operations
        can_execute, _, _ = cost_caps_service.can_execute_operation("semrush", 2.0)
        assert can_execute is True
    
    def test_cost_cap_report_with_real_data(self, cost_tracker, cost_caps_service):
        """Test cost cap report generation with real cost data."""
        # Add costs to multiple services
        cost_tracker.add_cost(8.0, "openai", "gpt-4")
        cost_tracker.add_cost(1.0, "openai", "gpt-3.5")
        cost_tracker.add_cost(4.0, "semrush", "domain-overview")
        cost_tracker.add_cost(0.5, "screenshot", "capture")
        
        # Generate report
        report = cost_caps_service.get_cost_cap_report()
        
        # Check summary
        summary = report["summary"]
        assert summary["total_daily_spent"] == 13.5  # 9 + 4 + 0.5
        assert summary["services_warning"] >= 1  # OpenAI should be in warning
        
        # Check individual service data
        services = report["services"]
        
        # OpenAI should be in warning state
        assert services["openai"]["daily_spent"] == 9.0
        assert services["openai"]["utilization_percent"] == 90.0
        assert services["openai"]["status"] == ServiceStatus.CRITICAL.value
        
        # Semrush should be in warning state (80% of 5.0 = 4.0)
        assert services["semrush"]["daily_spent"] == 4.0
        assert services["semrush"]["utilization_percent"] == 80.0
        assert services["semrush"]["status"] == ServiceStatus.WARNING.value
        
        # Screenshot should be available
        assert services["screenshot"]["daily_spent"] == 0.5
        assert services["screenshot"]["status"] == ServiceStatus.AVAILABLE.value
    
    def test_remaining_capacity_estimation(self, cost_tracker, cost_caps_service):
        """Test remaining capacity estimation with real cost data."""
        # Add some costs with multiple operations
        cost_tracker.add_cost(2.0, "openai", "gpt-4")
        cost_tracker.add_cost(1.0, "openai", "gpt-3.5")
        cost_tracker.add_cost(1.5, "openai", "gpt-4")
        
        # Estimate remaining capacity
        capacity = cost_caps_service.estimate_remaining_capacity("openai")
        
        assert capacity["service"] == "openai"
        assert capacity["remaining_budget"] == 5.5  # 10.0 - 4.5
        assert capacity["estimated_operations"] > 0
        assert "time_until_cap" in capacity
        assert capacity["current_burn_rate"] >= 0
    
    def test_enforcement_disabled_integration(self, cost_tracker):
        """Test that operations proceed when enforcement is disabled."""
        with patch.dict(os.environ, {
            "OPENAI_DAILY_CAP": "1.0",  # Very low cap
            "ENFORCE_SERVICE_COST_CAPS": "false",  # Disabled
        }):
            with patch("leadfactory.cost.per_service_cost_caps.cost_tracker", cost_tracker):
                cost_caps_service = PerServiceCostCaps()
                
                # Add costs over the limit
                cost_tracker.add_cost(2.0, "openai", "gpt-4")
                
                # Should still be able to execute operations when enforcement is disabled
                can_execute, reason, status = cost_caps_service.can_execute_operation("openai", 1.0)
                assert can_execute is True
                assert "enforcement disabled" in reason
    
    def test_cost_breakdown_integration(self, cost_tracker, cost_caps_service):
        """Test integration with cost breakdown functionality."""
        # Add costs with different operations
        cost_tracker.add_cost(3.0, "openai", "gpt-4")
        cost_tracker.add_cost(2.0, "openai", "gpt-3.5")
        cost_tracker.add_cost(1.0, "openai", "dall-e-3")
        
        # Get cost breakdown
        breakdown = cost_tracker.get_daily_cost_breakdown()
        
        assert "openai" in breakdown
        assert breakdown["openai"]["gpt-4"] == 3.0
        assert breakdown["openai"]["gpt-3.5"] == 2.0
        assert breakdown["openai"]["dall-e-3"] == 1.0
        
        # Check that service status reflects total
        status = cost_caps_service.get_service_status("openai")
        assert status.daily_spent == 6.0
        assert status.utilization_percent == 60.0


if __name__ == "__main__":
    pytest.main([__file__])