"""
Unit tests for automated bounce rate monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from leadfactory.email.sendgrid_warmup import WarmupStatus
from leadfactory.monitoring.bounce_rate_monitor import (
    AutomatedBounceMonitor,
    start_automated_monitoring,
    stop_automated_monitoring,
)
from leadfactory.services.bounce_monitor import IPSubuserStats


class TestAutomatedBounceMonitor:
    """Test automated bounce rate monitoring."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services."""
        bounce_monitor = MagicMock()
        bounce_monitor.config = MagicMock(
            minimum_sample_size=10,
            warning_threshold=0.05,
            critical_threshold=0.10,
            block_threshold=0.15
        )
        
        warmup_scheduler = MagicMock()
        rotation_service = MagicMock()
        warmup_integration = MagicMock()
        
        return {
            'bounce_monitor': bounce_monitor,
            'warmup_scheduler': warmup_scheduler,
            'rotation_service': rotation_service,
            'warmup_integration': warmup_integration
        }
    
    @pytest.fixture
    def monitor(self, mock_services):
        """Create monitor instance."""
        return AutomatedBounceMonitor(
            bounce_monitor=mock_services['bounce_monitor'],
            warmup_scheduler=mock_services['warmup_scheduler'],
            rotation_service=mock_services['rotation_service'],
            warmup_integration=mock_services['warmup_integration'],
            check_interval_seconds=1,  # Fast for testing
            alert_webhook_url=None
        )
    
    @pytest.mark.asyncio
    async def test_start_stop(self, monitor):
        """Test starting and stopping the monitor."""
        # Start
        await monitor.start()
        assert monitor._running is True
        assert monitor._task is not None
        
        # Stop
        await monitor.stop()
        assert monitor._running is False
        
    @pytest.mark.asyncio
    async def test_check_bounce_rates_healthy(self, monitor, mock_services):
        """Test checking bounce rates when all are healthy."""
        # Mock healthy stats
        healthy_stats = IPSubuserStats(
            ip_address='192.168.1.1',
            subuser='primary',
            total_sent=1000,
            total_bounced=20,
            bounce_rate=0.02  # 2% - healthy
        )
        
        monitor._get_all_stats = AsyncMock(return_value=[healthy_stats])
        monitor._clear_alerts = AsyncMock()
        
        await monitor._check_bounce_rates()
        
        # Should clear alerts for healthy IP
        monitor._clear_alerts.assert_called_once_with('192.168.1.1', 'primary')
        
    @pytest.mark.asyncio
    async def test_check_bounce_rates_warning(self, monitor, mock_services):
        """Test warning threshold handling."""
        # Mock warning-level stats
        warning_stats = IPSubuserStats(
            ip_address='192.168.1.1',
            subuser='primary',
            total_sent=1000,
            total_bounced=60,
            bounce_rate=0.06  # 6% - warning
        )
        
        monitor._get_all_stats = AsyncMock(return_value=[warning_stats])
        monitor._handle_warning_threshold = AsyncMock()
        
        await monitor._check_bounce_rates()
        
        monitor._handle_warning_threshold.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_check_bounce_rates_critical(self, monitor, mock_services):
        """Test critical threshold handling."""
        # Mock critical-level stats
        critical_stats = IPSubuserStats(
            ip_address='192.168.1.1',
            subuser='primary',
            total_sent=1000,
            total_bounced=120,
            bounce_rate=0.12  # 12% - critical
        )
        
        monitor._get_all_stats = AsyncMock(return_value=[critical_stats])
        monitor._handle_critical_threshold = AsyncMock()
        
        await monitor._check_bounce_rates()
        
        monitor._handle_critical_threshold.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_check_bounce_rates_block(self, monitor, mock_services):
        """Test block threshold handling."""
        # Mock block-level stats
        block_stats = IPSubuserStats(
            ip_address='192.168.1.1',
            subuser='primary',
            total_sent=1000,
            total_bounced=180,
            bounce_rate=0.18  # 18% - block
        )
        
        monitor._get_all_stats = AsyncMock(return_value=[block_stats])
        monitor._handle_block_threshold = AsyncMock()
        
        await monitor._check_bounce_rates()
        
        monitor._handle_block_threshold.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_handle_block_threshold_warmup(self, monitor, mock_services):
        """Test block threshold handling for IP in warmup."""
        stats = IPSubuserStats(
            ip_address='192.168.1.1',
            subuser='primary',
            total_sent=1000,
            total_bounced=180,
            bounce_rate=0.18
        )
        
        # Mock IP in warmup
        mock_services['warmup_scheduler'].get_warmup_status.return_value = MagicMock(
            status=WarmupStatus.IN_PROGRESS
        )
        monitor._send_alert = AsyncMock()
        
        await monitor._handle_block_threshold('192.168.1.1', 'primary', 0.18, stats)
        
        # Should pause warmup
        mock_services['warmup_scheduler'].pause_warmup.assert_called_once()
        monitor._send_alert.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_handle_block_threshold_production(self, monitor, mock_services):
        """Test block threshold handling for production IP."""
        stats = IPSubuserStats(
            ip_address='192.168.1.1',
            subuser='primary',
            total_sent=1000,
            total_bounced=180,
            bounce_rate=0.18
        )
        
        # Mock IP not in warmup
        mock_services['warmup_scheduler'].get_warmup_status.return_value = None
        
        # Mock IP in rotation pool
        from leadfactory.services.ip_rotation import IPSubuserPool, IPSubuserStatus
        mock_ip = MagicMock(spec=IPSubuserPool)
        mock_ip.ip_address = '192.168.1.1'
        mock_ip.subuser = 'primary'
        mock_ip.status = IPSubuserStatus.ACTIVE
        mock_ip.metadata = {}
        
        mock_pool = MagicMock()
        mock_pool.pool = [mock_ip]
        
        mock_services['rotation_service'].get_all_pools.return_value = [mock_pool]
        mock_services['rotation_service'].alerting_service = None
        monitor._send_alert = AsyncMock()
        
        await monitor._handle_block_threshold('192.168.1.1', 'primary', 0.18, stats)
        
        # Should disable IP
        assert mock_ip.status == IPSubuserStatus.DISABLED
        assert 'disabled_reason' in mock_ip.metadata
        assert 'High bounce rate: 18.00%' in mock_ip.metadata['disabled_reason']
        monitor._send_alert.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_send_alert_logging(self, monitor):
        """Test alert logging."""
        with patch('leadfactory.monitoring.bounce_rate_monitor.logger') as mock_logger:
            await monitor._send_alert('critical', 'Test Alert', 'Test message')
            mock_logger.error.assert_called_once()
            
            await monitor._send_alert('warning', 'Test Alert', 'Test message')
            mock_logger.warning.assert_called_once()
            
            await monitor._send_alert('info', 'Test Alert', 'Test message')
            mock_logger.info.assert_called()
            
    @pytest.mark.asyncio
    async def test_send_alert_webhook(self, monitor):
        """Test alert webhook sending."""
        monitor.alert_webhook_url = 'https://example.com/webhook'
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            await monitor._send_alert('critical', 'Test Alert', 'Test message')
            
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert call_args[0][0] == 'https://example.com/webhook'
            assert 'json' in call_args[1]
            assert call_args[1]['json']['severity'] == 'critical'
            
    def test_get_monitoring_status(self, monitor):
        """Test getting monitoring status."""
        monitor._running = True
        monitor._alert_history = {
            '192.168.1.1:primary': {
                'bounce_rate': 0.12,
                'timestamp': datetime.now()
            }
        }
        
        status = monitor.get_monitoring_status()
        
        assert status['running'] is True
        assert status['check_interval_seconds'] == 1
        assert status['active_alerts'] == 1
        assert len(status['alert_history']) == 1
        assert status['alert_history'][0]['ip_subuser'] == '192.168.1.1:primary'
        
    @pytest.mark.asyncio
    async def test_monitor_loop_error_handling(self, monitor):
        """Test error handling in monitor loop."""
        monitor._check_bounce_rates = AsyncMock(side_effect=Exception("Test error"))
        
        # Start monitoring
        await monitor.start()
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Should still be running despite error
        assert monitor._running is True
        
        # Stop
        await monitor.stop()
        
    @pytest.mark.asyncio
    async def test_skip_insufficient_samples(self, monitor):
        """Test skipping IPs with insufficient samples."""
        # Mock stats with low sample size
        low_sample_stats = IPSubuserStats(
            ip_address='192.168.1.1',
            subuser='primary',
            total_sent=5,  # Below minimum
            total_bounced=2,
            bounce_rate=0.4  # High rate but low samples
        )
        
        monitor._get_all_stats = AsyncMock(return_value=[low_sample_stats])
        monitor._handle_block_threshold = AsyncMock()
        
        await monitor._check_bounce_rates()
        
        # Should not trigger any threshold handlers
        monitor._handle_block_threshold.assert_not_called()


class TestMonitoringSingleton:
    """Test monitoring singleton functions."""
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring via singleton."""
        with patch('leadfactory.monitoring.bounce_rate_monitor.BounceRateMonitor'):
            with patch('leadfactory.monitoring.bounce_rate_monitor.IPRotationService'):
                with patch('leadfactory.monitoring.bounce_rate_monitor.SendGridWarmupScheduler'):
                    with patch('leadfactory.monitoring.bounce_rate_monitor.SendGridWarmupIntegration'):
                        # Start monitoring
                        monitor = await start_automated_monitoring(check_interval_seconds=1)
                        assert monitor is not None
                        assert monitor._running is True
                        
                        # Try starting again - should return existing
                        monitor2 = await start_automated_monitoring()
                        assert monitor2 is monitor
                        
                        # Stop monitoring
                        await stop_automated_monitoring()
                        
    @pytest.mark.asyncio
    async def test_get_automated_monitor(self):
        """Test getting monitor instance."""
        from leadfactory.monitoring.bounce_rate_monitor import get_automated_monitor
        
        # Should be None initially
        assert get_automated_monitor() is None
        
        with patch('leadfactory.monitoring.bounce_rate_monitor.BounceRateMonitor'):
            with patch('leadfactory.monitoring.bounce_rate_monitor.IPRotationService'):
                with patch('leadfactory.monitoring.bounce_rate_monitor.SendGridWarmupScheduler'):
                    with patch('leadfactory.monitoring.bounce_rate_monitor.SendGridWarmupIntegration'):
                        # Start monitoring
                        monitor = await start_automated_monitoring(check_interval_seconds=1)
                        
                        # Should return the instance
                        assert get_automated_monitor() is monitor
                        
                        # Stop
                        await stop_automated_monitoring()
                        
                        # Should be None again
                        assert get_automated_monitor() is None