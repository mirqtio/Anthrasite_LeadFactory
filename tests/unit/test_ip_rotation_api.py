"""
Unit tests for IP rotation API endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from leadfactory.api.ip_rotation_api import (
    ConfigurationUpdate,
    IPSubuserRequest,
    RotationRequest,
    get_alerting_service,
    get_rotation_service,
    router,
)
from leadfactory.services.ip_rotation import (
    IPRotationService,
    IPSubuserPool,
    IPSubuserStatus,
    RotationConfig,
    RotationEvent,
    RotationReason,
)
from leadfactory.services.ip_rotation_alerting import (
    Alert,
    AlertingConfig,
    AlertSeverity,
    AlertType,
    IPRotationAlerting,
)


class TestAPIModels:
    """Test API request/response models."""

    def test_ip_subuser_request(self):
        """Test IPSubuserRequest model."""
        request = IPSubuserRequest(
            ip_address="192.168.1.1",
            subuser="test_user",
            priority=2,
            tags=["production", "high-volume"],
            metadata={"region": "us-east-1"},
        )

        assert request.ip_address == "192.168.1.1"
        assert request.subuser == "test_user"
        assert request.priority == 2
        assert request.tags == ["production", "high-volume"]
        assert request.metadata == {"region": "us-east-1"}

    def test_rotation_request(self):
        """Test RotationRequest model."""
        request = RotationRequest(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason="manual",
        )

        assert request.from_ip == "192.168.1.1"
        assert request.from_subuser == "user1"
        assert request.to_ip == "192.168.1.2"
        assert request.to_subuser == "user2"
        assert request.reason == "manual"

    def test_config_update_request(self):
        """Test ConfigurationUpdate model."""
        request = ConfigurationUpdate(
            enable_automatic_rotation=False,
            default_bounce_threshold=0.08,
            default_cooldown_hours=6,
            rotation_delay_seconds=30,
        )

        assert request.enable_automatic_rotation is False
        assert request.default_bounce_threshold == 0.08
        assert request.default_cooldown_hours == 6
        assert request.rotation_delay_seconds == 30


class TestIPRotationAPI:
    """Test IP rotation API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock services
        self.mock_rotation_service = Mock(spec=IPRotationService)
        self.mock_alerting_service = Mock(spec=IPRotationAlerting)

        # Override dependency injection
        router.dependency_overrides[get_rotation_service] = (
            lambda: self.mock_rotation_service
        )
        router.dependency_overrides[get_alerting_service] = (
            lambda: self.mock_alerting_service
        )

        # Create test client
        self.client = TestClient(router)

    def teardown_method(self):
        """Clean up after tests."""
        router.dependency_overrides.clear()

    def test_get_system_status(self):
        """Test GET /status endpoint."""
        # Mock service responses
        self.mock_rotation_service.get_pool_status.return_value = [
            {
                "ip_address": "192.168.1.1",
                "subuser": "user1",
                "status": "active",
                "performance_score": 0.95,
            }
        ]
        self.mock_alerting_service.get_dashboard_data.return_value = {
            "system_status": {"health": "healthy", "total_rotations": 10},
            "circuit_breaker_status": {"state": "closed", "can_execute": True},
        }

        response = self.client.get("/status")

        assert response.status_code == 200
        data = response.json()
        assert "pool_status" in data
        assert "dashboard_data" in data
        assert data["pool_status"][0]["ip_address"] == "192.168.1.1"

    def test_add_ip_subuser(self):
        """Test POST /pool/add endpoint."""
        request_data = {
            "ip_address": "192.168.1.1",
            "subuser": "test_user",
            "priority": 2,
            "tags": ["production"],
            "metadata": {"region": "us-east-1"},
        }

        response = self.client.post("/pool/add", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "IP/subuser added successfully"

        # Verify service was called correctly
        self.mock_rotation_service.add_ip_subuser.assert_called_once_with(
            ip_address="192.168.1.1",
            subuser="test_user",
            priority=2,
            tags=["production"],
            metadata={"region": "us-east-1"},
        )

    def test_add_ip_subuser_error(self):
        """Test POST /pool/add endpoint with service error."""
        self.mock_rotation_service.add_ip_subuser.side_effect = ValueError(
            "IP already exists"
        )

        request_data = {
            "ip_address": "192.168.1.1",
            "subuser": "test_user",
        }

        response = self.client.post("/pool/add", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert "IP already exists" in data["detail"]

    def test_remove_ip_subuser(self):
        """Test DELETE /pool/remove endpoint."""
        response = self.client.delete("/pool/remove/192.168.1.1/test_user")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "IP/subuser removed successfully"

        # Verify service was called correctly
        self.mock_rotation_service.remove_ip_subuser.assert_called_once_with(
            "192.168.1.1", "test_user"
        )

    def test_remove_ip_subuser_not_found(self):
        """Test DELETE /pool/remove endpoint with not found error."""
        self.mock_rotation_service.remove_ip_subuser.side_effect = ValueError(
            "IP/subuser not found"
        )

        response = self.client.delete("/pool/remove/192.168.1.1/test_user")

        assert response.status_code == 404
        data = response.json()
        assert "IP/subuser not found" in data["detail"]

    def test_execute_rotation(self):
        """Test POST /rotation/execute endpoint."""
        # Mock successful rotation
        rotation_event = RotationEvent(
            timestamp=datetime.now(),
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL,
            success=True,
        )
        self.mock_rotation_service.execute_rotation.return_value = rotation_event

        request_data = {
            "from_ip": "192.168.1.1",
            "from_subuser": "user1",
            "to_ip": "192.168.1.2",
            "to_subuser": "user2",
            "reason": "manual",
        }

        response = self.client.post("/rotation/execute", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["from_ip"] == "192.168.1.1"
        assert data["to_ip"] == "192.168.1.2"

    def test_execute_rotation_error(self):
        """Test POST /rotation/execute endpoint with rotation error."""
        self.mock_rotation_service.execute_rotation.side_effect = ValueError(
            "Target IP in cooldown"
        )

        request_data = {
            "from_ip": "192.168.1.1",
            "from_subuser": "user1",
            "to_ip": "192.168.1.2",
            "to_subuser": "user2",
            "reason": "manual",
        }

        response = self.client.post("/rotation/execute", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert "Target IP in cooldown" in data["detail"]

    def test_get_config(self):
        """Test GET /config endpoint."""
        mock_config = RotationConfig(
            enable_automatic_rotation=True,
            default_bounce_threshold=0.05,
            default_cooldown_hours=4,
            rotation_delay_seconds=10,
        )
        self.mock_rotation_service.config = mock_config

        response = self.client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert data["enable_automatic_rotation"] is True
        assert data["default_bounce_threshold"] == 0.05
        assert data["default_cooldown_hours"] == 4

    def test_update_config(self):
        """Test PUT /config endpoint."""
        mock_config = RotationConfig()
        self.mock_rotation_service.config = mock_config

        request_data = {
            "enable_automatic_rotation": False,
            "default_bounce_threshold": 0.08,
            "default_cooldown_hours": 6,
        }

        response = self.client.put("/config", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Configuration updated successfully"

        # Verify config was updated
        assert mock_config.enable_automatic_rotation is False
        assert mock_config.default_bounce_threshold == 0.08
        assert mock_config.default_cooldown_hours == 6

    def test_reset_circuit_breaker(self):
        """Test POST /circuit-breaker/reset endpoint."""
        response = self.client.post("/circuit-breaker/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Circuit breaker reset successfully"

        # Verify service was called
        self.mock_alerting_service.circuit_breaker.reset.assert_called_once()

    def test_get_alerts_summary(self):
        """Test GET /alerts/summary endpoint."""
        mock_summary = {
            "total_alerts": 5,
            "alerts_by_severity": {"info": 3, "warning": 2},
            "alerts_by_type": {"rotation_executed": 3, "threshold_breach": 2},
        }
        self.mock_alerting_service.get_alert_summary.return_value = mock_summary

        response = self.client.get("/alerts/summary?hours=24")

        assert response.status_code == 200
        data = response.json()
        assert data["total_alerts"] == 5
        assert data["alerts_by_severity"]["info"] == 3

        # Verify service was called with correct parameter
        self.mock_alerting_service.get_alert_summary.assert_called_once_with(24)

    def test_get_dashboard_data(self):
        """Test GET /dashboard endpoint."""
        mock_dashboard_data = {
            "system_status": {"health": "healthy", "total_rotations": 10},
            "recent_alerts": [],
            "circuit_breaker_status": {"state": "closed"},
            "metrics": {"alerts_by_severity": {"info": 5}},
        }
        self.mock_alerting_service.get_dashboard_data.return_value = mock_dashboard_data

        response = self.client.get("/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["system_status"]["health"] == "healthy"
        assert data["system_status"]["total_rotations"] == 10

    def test_toggle_maintenance_mode(self):
        """Test POST /pool/{ip_address}/{subuser}/maintenance endpoint."""
        # Mock getting pool entry
        mock_pool_entry = Mock()
        mock_pool_entry.status = IPSubuserStatus.ACTIVE
        self.mock_rotation_service.get_ip_subuser_pool.return_value = mock_pool_entry

        response = self.client.post(
            "/pool/192.168.1.1/test_user/maintenance?enabled=true"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Maintenance mode enabled for IP/subuser"

        # Verify pool entry was updated
        assert mock_pool_entry.status == IPSubuserStatus.MAINTENANCE

    def test_toggle_maintenance_mode_not_found(self):
        """Test maintenance mode toggle with non-existent IP/subuser."""
        self.mock_rotation_service.get_ip_subuser_pool.return_value = None

        response = self.client.post(
            "/pool/192.168.1.1/test_user/maintenance?enabled=true"
        )

        assert response.status_code == 404
        data = response.json()
        assert "IP/subuser not found" in data["detail"]

    def test_cleanup_old_data(self):
        """Test POST /cleanup endpoint."""
        self.mock_rotation_service.cleanup_old_rotation_events.return_value = 5
        self.mock_alerting_service.cleanup_old_alerts.return_value = 3

        response = self.client.post("/cleanup?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Cleanup completed successfully"
        assert data["rotation_events_removed"] == 5
        assert data["alerts_removed"] == 3

        # Verify services were called with correct parameter
        self.mock_rotation_service.cleanup_old_rotation_events.assert_called_once_with(
            30
        )
        self.mock_alerting_service.cleanup_old_alerts.assert_called_once_with(30)

    def test_api_error_handling(self):
        """Test API error handling for unexpected exceptions."""
        self.mock_rotation_service.get_pool_status.side_effect = Exception(
            "Unexpected error"
        )

        response = self.client.get("/status")

        assert response.status_code == 500
        data = response.json()
        assert "Internal server error" in data["detail"]

    def test_api_validation_error(self):
        """Test API validation error handling."""
        # Send invalid request data
        request_data = {
            "ip_address": "",  # Empty IP address should fail validation
            "subuser": "test_user",
        }

        response = self.client.post("/pool/add", json=request_data)

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    def test_api_dependency_injection(self):
        """Test that dependency injection works correctly."""
        # This test verifies that the dependency injection system
        # correctly provides the mocked services
        response = self.client.get("/status")

        # The fact that our mocked methods are called proves
        # dependency injection is working
        self.mock_rotation_service.get_pool_status.assert_called_once()
        self.mock_alerting_service.get_dashboard_data.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
