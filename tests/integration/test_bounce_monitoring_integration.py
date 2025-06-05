"""
Integration tests for automated bounce monitoring with warmup and rotation.
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.email.sendgrid_warmup import SendGridWarmupScheduler, WarmupStatus
from leadfactory.monitoring.bounce_rate_monitor import AutomatedBounceMonitor
from leadfactory.services.bounce_monitor import (
    BounceEvent,
    BounceRateConfig,
    BounceRateMonitor,
)
from leadfactory.services.ip_rotation import (
    IPRotationService,
    IPSubuserPool,
    IPSubuserStatus,
    RotationConfig,
)


class TestBounceMonitoringIntegration:
    """Test integration between bounce monitoring, warmup, and rotation."""

    @pytest.fixture
    def services(self):
        """Create real service instances."""
        # Use in-memory database for testing
        bounce_config = BounceRateConfig(
            minimum_sample_size=5,  # Lower for testing
            warning_threshold=0.05,
            critical_threshold=0.10,
            block_threshold=0.15
        )
        bounce_monitor = BounceRateMonitor(config=bounce_config, db_path=":memory:")

        rotation_config = RotationConfig()
        rotation_service = IPRotationService(config=rotation_config)

        warmup_scheduler = SendGridWarmupScheduler(db_path=":memory:")

        return {
            "bounce_monitor": bounce_monitor,
            "rotation_service": rotation_service,
            "warmup_scheduler": warmup_scheduler
        }

    @pytest.fixture
    def monitor(self, services):
        """Create monitor with real services."""
        from leadfactory.email.sendgrid_warmup_integration import (
            SendGridWarmupIntegration,
            WarmupIntegrationConfig,
        )

        integration = SendGridWarmupIntegration(
            warmup_scheduler=services["warmup_scheduler"],
            bounce_monitor=services["bounce_monitor"],
            rotation_service=services["rotation_service"],
            config=WarmupIntegrationConfig()
        )

        return AutomatedBounceMonitor(
            bounce_monitor=services["bounce_monitor"],
            warmup_scheduler=services["warmup_scheduler"],
            rotation_service=services["rotation_service"],
            warmup_integration=integration,
            check_interval_seconds=0.1  # Very fast for testing
        )

    @pytest.mark.asyncio
    async def test_warmup_ip_high_bounce_pauses(self, monitor, services):
        """Test that high bounce rate pauses warmup."""
        # Start warmup for an IP
        services["warmup_scheduler"].start_warmup("192.168.1.1", "warmup_user")

        # Simulate sends
        for _ in range(100):
            services["bounce_monitor"].record_send("192.168.1.1", "warmup_user")

        # Simulate high bounce rate (20 bounces = 20%)
        for i in range(20):
            bounce_event = BounceEvent(
                email=f"test{i}@example.com",
                ip_address="192.168.1.1",
                subuser="warmup_user",
                bounce_type="hard",
                reason="Invalid recipient"
            )
            services["bounce_monitor"].record_bounce(bounce_event)

        # Run monitoring check
        await monitor._check_bounce_rates()

        # Check warmup was paused
        status = services["warmup_scheduler"].get_warmup_status("192.168.1.1")
        assert status.status == WarmupStatus.PAUSED

    @pytest.mark.asyncio
    async def test_production_ip_high_bounce_removes(self, monitor, services):
        """Test that high bounce rate removes production IP from rotation."""
        # Add IP to production rotation pool
        services["rotation_service"].add_ip_subuser("192.168.1.2", "prod_user")

        # Simulate sends
        for _ in range(100):
            services["bounce_monitor"].record_send("192.168.1.2", "prod_user")

        # Simulate high bounce rate (18 bounces = 18%)
        for i in range(18):
            bounce_event = BounceEvent(
                email=f"test{i}@example.com",
                ip_address="192.168.1.2",
                subuser="prod_user",
                bounce_type="hard",
                reason="Invalid recipient"
            )
            services["bounce_monitor"].record_bounce(bounce_event)

        # Run monitoring check
        await monitor._check_bounce_rates()

        # Check IP was marked as failed
        pool = services["rotation_service"].get_pool("production")
        ip_status = next(
            (ip for ip in pool.pool if ip.ip_address == "192.168.1.2"),
            None
        )
        assert ip_status is not None
        assert ip_status.status == IPSubuserStatus.FAILED

    @pytest.mark.asyncio
    async def test_critical_threshold_deprioritizes(self, monitor, services):
        """Test that critical threshold deprioritizes IP."""
        # Add IP to rotation pool
        services["rotation_service"].create_pool("main", [("192.168.1.3", "user3")])

        # Simulate sends
        for _ in range(100):
            services["bounce_monitor"].record_send("192.168.1.3", "user3")

        # Simulate critical bounce rate (12 bounces = 12%)
        for i in range(12):
            bounce_event = BounceEvent(
                email=f"test{i}@example.com",
                ip_address="192.168.1.3",
                subuser="user3",
                bounce_type="soft",
                reason="Mailbox full"
            )
            services["bounce_monitor"].record_bounce(bounce_event)

        # Run monitoring check
        await monitor._check_bounce_rates()

        # Check IP was deprioritized
        pool = services["rotation_service"].get_pool("main")
        ip_status = next(
            (ip for ip in pool.pool if ip.ip_address == "192.168.1.3"),
            None
        )
        assert ip_status is not None
        assert ip_status.priority > 1  # Lower priority

    @pytest.mark.asyncio
    async def test_monitoring_lifecycle(self, monitor, services):
        """Test full monitoring lifecycle."""
        # Start monitoring
        await monitor.start()
        assert monitor._running is True

        # Add some test data
        services["rotation_service"].create_pool("test", [("192.168.1.4", "user4")])

        # Let it run for a moment
        await asyncio.sleep(0.2)

        # Check status
        status = monitor.get_monitoring_status()
        assert status["running"] is True

        # Stop monitoring
        await monitor.stop()
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_alert_history_tracking(self, monitor, services):
        """Test that alert history is tracked correctly."""
        # Add IP to rotation
        services["rotation_service"].create_pool("test", [("192.168.1.5", "user5")])

        # Create warning-level bounce rate
        for _ in range(100):
            services["bounce_monitor"].record_send("192.168.1.5", "user5")
        for _ in range(6):
            services["bounce_monitor"].record_bounce(
                BounceEvent(
                    email="test@example.com",
                    ip_address="192.168.1.5",
                    subuser="user5",
                    bounce_type="soft"
                )
            )

        # Check bounce rates
        await monitor._check_bounce_rates()

        # Check alert history
        assert "192.168.1.5:user5" in monitor._alert_history
        alert = monitor._alert_history["192.168.1.5:user5"]
        assert alert["bounce_rate"] == 0.06

    @pytest.mark.asyncio
    async def test_healthy_ip_clears_alerts(self, monitor, services):
        """Test that healthy IPs clear previous alerts."""
        # Add alert history
        monitor._alert_history["192.168.1.6:user6"] = {
            "bounce_rate": 0.08,
            "timestamp": datetime.now()
        }

        # Add IP with healthy bounce rate
        services["rotation_service"].create_pool("test", [("192.168.1.6", "user6")])
        for _ in range(100):
            services["bounce_monitor"].record_send("192.168.1.6", "user6")
        # Only 2 bounces = 2% (healthy)
        for _ in range(2):
            services["bounce_monitor"].record_bounce(
                BounceEvent(
                    email="test@example.com",
                    ip_address="192.168.1.6",
                    subuser="user6",
                    bounce_type="soft"
                )
            )

        # Check bounce rates
        await monitor._check_bounce_rates()

        # Alert should be cleared
        assert "192.168.1.6:user6" not in monitor._alert_history

    @pytest.mark.asyncio
    async def test_insufficient_samples_ignored(self, monitor, services):
        """Test that IPs with insufficient samples are ignored."""
        # Add IP with very few sends
        services["rotation_service"].create_pool("test", [("192.168.1.7", "user7")])

        # Only 3 sends (below minimum sample size of 5)
        for _ in range(3):
            services["bounce_monitor"].record_send("192.168.1.7", "user7")
        # 2 bounces would be 66% but should be ignored
        for _ in range(2):
            services["bounce_monitor"].record_bounce(
                BounceEvent(
                    email="test@example.com",
                    ip_address="192.168.1.7",
                    subuser="user7",
                    bounce_type="hard"
                )
            )

        # Mock alert handler to verify it's not called
        monitor._handle_block_threshold = MagicMock()

        # Check bounce rates
        await monitor._check_bounce_rates()

        # Should not trigger any alerts
        monitor._handle_block_threshold.assert_not_called()


class TestMonitoringCLI:
    """Test monitoring CLI commands."""

    @pytest.mark.asyncio
    async def test_cli_start_stop(self):
        """Test CLI start/stop commands."""
        from click.testing import CliRunner

        from leadfactory.cli.commands.monitoring_commands import (
            monitoring,
            start_bounce_monitor,
            stop_bounce_monitor,
        )

        runner = CliRunner()

        with patch("leadfactory.monitoring.bounce_rate_monitor.start_automated_monitoring") as mock_start:
            with patch("leadfactory.monitoring.bounce_rate_monitor.stop_automated_monitoring") as mock_stop:
                # Mock the async functions
                mock_start.return_value = asyncio.Future()
                mock_start.return_value.set_result(MagicMock(_running=True))

                mock_stop.return_value = asyncio.Future()
                mock_stop.return_value.set_result(None)

                # Test start command
                result = runner.invoke(start_bounce_monitor, ["--interval", "60"])
                assert result.exit_code == 0
                assert "started" in result.output.lower()

                # Test stop command
                result = runner.invoke(stop_bounce_monitor)
                assert result.exit_code == 0
                assert "stopped" in result.output.lower()
