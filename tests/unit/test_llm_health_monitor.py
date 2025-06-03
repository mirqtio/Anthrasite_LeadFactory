"""
Tests for LLM Health Monitoring System
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from leadfactory.llm.health_monitor import (
    HealthMonitor,
    HealthConfig,
    HealthStatus,
    AlertSeverity,
    HealthCheckResult,
    ProviderMetrics,
    HealthAlert
)
from leadfactory.llm.provider import LLMProvider, LLMHealthStatus


@pytest.fixture
def event_loop():
    """Create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def health_config():
    """Create a test health configuration."""
    return HealthConfig(
        check_interval=1.0,  # Fast checks for testing
        timeout=5.0,
        failure_threshold=2,
        recovery_threshold=1,
        response_time_threshold=2.0,
        enable_alerts=True,
        max_history_size=100
    )


@pytest.fixture
def health_monitor(health_config):
    """Create a health monitor instance."""
    return HealthMonitor(health_config)


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = AsyncMock(spec=LLMProvider)
    provider.check_health = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_health_monitor_initialization(health_config):
    """Test health monitor initialization."""
    monitor = HealthMonitor(health_config)

    assert monitor.config == health_config
    assert monitor.providers == {}
    assert monitor.health_history == []
    assert monitor.provider_metrics == {}
    assert monitor.active_alerts == {}
    assert monitor._monitoring_task is None


@pytest.mark.asyncio
async def test_register_provider(health_monitor, mock_provider):
    """Test provider registration."""
    health_monitor.register_provider("test_provider", mock_provider)

    assert "test_provider" in health_monitor.providers
    assert health_monitor.providers["test_provider"] == mock_provider
    assert "test_provider" in health_monitor.provider_metrics
    assert health_monitor.provider_metrics["test_provider"].provider == "test_provider"


@pytest.mark.asyncio
async def test_unregister_provider(health_monitor, mock_provider):
    """Test provider unregistration."""
    health_monitor.register_provider("test_provider", mock_provider)
    health_monitor.unregister_provider("test_provider")

    assert "test_provider" not in health_monitor.providers


@pytest.mark.asyncio
async def test_check_provider_health_success(health_monitor, mock_provider):
    """Test successful health check."""
    # Setup mock
    health_status = LLMHealthStatus(
        is_healthy=True,
        provider="test_provider",
        last_check=time.time(),
        response_time=1.0
    )
    mock_provider.check_health.return_value = health_status

    # Register provider and check health
    health_monitor.register_provider("test_provider", mock_provider)
    result = await health_monitor.check_provider_health("test_provider")

    assert result.provider == "test_provider"
    assert result.status == HealthStatus.HEALTHY
    assert result.response_time > 0
    assert result.error_message is None
    assert "provider_is_healthy" in result.metadata


@pytest.mark.asyncio
async def test_check_provider_health_unhealthy(health_monitor, mock_provider):
    """Test unhealthy provider health check."""
    # Setup mock
    health_status = LLMHealthStatus(
        is_healthy=False,
        provider="test_provider",
        last_check=time.time(),
        error_message="Provider is down"
    )
    mock_provider.check_health.return_value = health_status

    # Register provider and check health
    health_monitor.register_provider("test_provider", mock_provider)
    result = await health_monitor.check_provider_health("test_provider")

    assert result.provider == "test_provider"
    assert result.status == HealthStatus.UNHEALTHY
    assert result.error_message is None
    assert result.metadata["provider_message"] == "Provider is down"


@pytest.mark.asyncio
async def test_check_provider_health_slow_response(health_monitor, mock_provider):
    """Test health check with slow response."""
    # Setup mock with delay
    async def slow_health_check():
        await asyncio.sleep(2.5)  # Longer than response_time_threshold
        return LLMHealthStatus(
            is_healthy=True,
            provider="test_provider",
            last_check=time.time()
        )

    mock_provider.check_health = slow_health_check

    # Register provider and check health
    health_monitor.register_provider("test_provider", mock_provider)
    result = await health_monitor.check_provider_health("test_provider")

    assert result.provider == "test_provider"
    assert result.status == HealthStatus.DEGRADED  # Healthy but slow
    assert result.response_time > 2.0


@pytest.mark.asyncio
async def test_check_provider_health_timeout(health_monitor, mock_provider):
    """Test health check timeout."""
    # Setup mock with long delay
    async def timeout_health_check():
        await asyncio.sleep(10)  # Longer than timeout
        return LLMHealthStatus(is_healthy=True, status="healthy")

    mock_provider.check_health = timeout_health_check

    # Register provider and check health
    health_monitor.register_provider("test_provider", mock_provider)
    result = await health_monitor.check_provider_health("test_provider")

    assert result.provider == "test_provider"
    assert result.status == HealthStatus.CRITICAL
    assert "timed out" in result.error_message.lower()


@pytest.mark.asyncio
async def test_check_provider_health_exception(health_monitor, mock_provider):
    """Test health check with exception."""
    # Setup mock to raise exception
    mock_provider.check_health.side_effect = Exception("Connection failed")

    # Register provider and check health
    health_monitor.register_provider("test_provider", mock_provider)
    result = await health_monitor.check_provider_health("test_provider")

    assert result.provider == "test_provider"
    assert result.status == HealthStatus.CRITICAL
    assert "Connection failed" in result.error_message


@pytest.mark.asyncio
async def test_check_provider_health_not_registered(health_monitor):
    """Test health check for unregistered provider."""
    with pytest.raises(ValueError, match="Provider test_provider is not registered"):
        await health_monitor.check_provider_health("test_provider")


@pytest.mark.asyncio
async def test_check_all_providers(health_monitor, mock_provider):
    """Test checking health of all providers."""
    # Setup multiple providers
    provider1 = AsyncMock(spec=LLMProvider)
    provider1.check_health.return_value = LLMHealthStatus(
        is_healthy=True,
        provider="provider1",
        last_check=time.time()
    )

    provider2 = AsyncMock(spec=LLMProvider)
    provider2.check_health.return_value = LLMHealthStatus(
        is_healthy=False,
        provider="provider2",
        last_check=time.time(),
        error_message="Provider is down"
    )

    health_monitor.register_provider("provider1", provider1)
    health_monitor.register_provider("provider2", provider2)

    results = await health_monitor.check_all_providers()

    assert len(results) == 2
    assert "provider1" in results
    assert "provider2" in results
    assert results["provider1"].status == HealthStatus.HEALTHY
    assert results["provider2"].status == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_metrics_update(health_monitor, mock_provider):
    """Test provider metrics updates."""
    # Setup mock
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=True,
        provider="test_provider",
        last_check=time.time()
    )

    # Register provider and perform multiple checks
    health_monitor.register_provider("test_provider", mock_provider)

    # First check (success)
    await health_monitor.check_provider_health("test_provider")
    metrics = health_monitor.provider_metrics["test_provider"]
    assert metrics.total_checks == 1
    assert metrics.successful_checks == 1
    assert metrics.failed_checks == 0
    assert metrics.consecutive_failures == 0
    assert metrics.uptime_percentage == 100.0

    # Second check (failure)
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=False,
        provider="test_provider",
        last_check=time.time(),
        error_message="Provider is down"
    )
    await health_monitor.check_provider_health("test_provider")

    metrics = health_monitor.provider_metrics["test_provider"]
    assert metrics.total_checks == 2
    assert metrics.successful_checks == 1
    assert metrics.failed_checks == 1
    assert metrics.consecutive_failures == 1
    assert metrics.uptime_percentage == 50.0


@pytest.mark.asyncio
async def test_alert_creation_consecutive_failures(health_monitor, mock_provider):
    """Test alert creation for consecutive failures."""
    # Setup mock to fail
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=False,
        provider="test_provider",
        last_check=time.time(),
        error_message="Provider is down"
    )

    health_monitor.register_provider("test_provider", mock_provider)

    # First failure - no alert yet
    await health_monitor.check_provider_health("test_provider")
    assert len(health_monitor.active_alerts) == 0

    # Second failure - should trigger alert
    await health_monitor.check_provider_health("test_provider")
    assert len(health_monitor.active_alerts) == 1

    alert_key = "test_provider_consecutive_failures"
    assert alert_key in health_monitor.active_alerts
    alert = health_monitor.active_alerts[alert_key]
    assert alert.provider == "test_provider"
    assert alert.severity == AlertSeverity.ERROR
    assert "consecutive failures" in alert.message


@pytest.mark.asyncio
async def test_alert_resolution(health_monitor, mock_provider):
    """Test alert resolution after recovery."""
    # Setup mock to fail initially
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=False,
        provider="test_provider",
        last_check=time.time(),
        error_message="Provider is down"
    )

    health_monitor.register_provider("test_provider", mock_provider)

    # Create alert with failures
    await health_monitor.check_provider_health("test_provider")
    await health_monitor.check_provider_health("test_provider")
    assert len(health_monitor.active_alerts) == 1

    # Recovery - should resolve alert
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=True,
        provider="test_provider",
        last_check=time.time()
    )
    await health_monitor.check_provider_health("test_provider")

    assert len(health_monitor.active_alerts) == 0


@pytest.mark.asyncio
async def test_slow_response_alert(health_monitor, mock_provider):
    """Test alert creation for slow responses."""
    # Setup mock with very slow response
    async def very_slow_health_check():
        await asyncio.sleep(4.5)  # Much longer than threshold * 2
        return LLMHealthStatus(
            is_healthy=True,
            provider="test_provider",
            last_check=time.time()
        )

    mock_provider.check_health = very_slow_health_check

    health_monitor.register_provider("test_provider", mock_provider)
    await health_monitor.check_provider_health("test_provider")

    # Should create slow response alert
    alert_key = "test_provider_slow_response"
    assert alert_key in health_monitor.active_alerts
    alert = health_monitor.active_alerts[alert_key]
    assert alert.severity == AlertSeverity.WARNING
    assert "slow response time" in alert.message


@pytest.mark.asyncio
async def test_get_provider_status(health_monitor, mock_provider):
    """Test getting provider status."""
    # Setup mock
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=True,
        provider="test_provider",
        last_check=time.time()
    )

    health_monitor.register_provider("test_provider", mock_provider)
    await health_monitor.check_provider_health("test_provider")

    status = await health_monitor.get_provider_status("test_provider")

    assert status["provider"] == "test_provider"
    assert "metrics" in status
    assert status["metrics"]["total_checks"] == 1
    assert status["metrics"]["successful_checks"] == 1
    assert status["current_status"] == "healthy"


@pytest.mark.asyncio
async def test_get_provider_status_not_found(health_monitor):
    """Test getting status for non-existent provider."""
    status = await health_monitor.get_provider_status("nonexistent")
    assert "error" in status


@pytest.mark.asyncio
async def test_dashboard_data(health_monitor, mock_provider):
    """Test getting dashboard data."""
    # Setup providers
    provider1 = AsyncMock(spec=LLMProvider)
    provider1.check_health.return_value = LLMHealthStatus(
        is_healthy=True,
        provider="provider1",
        last_check=time.time()
    )

    provider2 = AsyncMock(spec=LLMProvider)
    provider2.check_health.return_value = LLMHealthStatus(
        is_healthy=False,
        provider="provider2",
        last_check=time.time(),
        error_message="Provider is down"
    )

    health_monitor.register_provider("provider1", provider1)
    health_monitor.register_provider("provider2", provider2)

    # Perform checks
    await health_monitor.check_all_providers()

    dashboard = await health_monitor.get_dashboard_data()

    assert dashboard["total_providers"] == 2
    assert dashboard["healthy_providers"] == 1
    assert dashboard["overall_health"] == "unhealthy"  # One unhealthy provider
    assert "providers" in dashboard
    assert "recent_alerts" in dashboard
    assert dashboard["monitoring_active"] is False


@pytest.mark.asyncio
async def test_alert_callbacks(health_monitor, mock_provider):
    """Test alert callback functionality."""
    callback_called = []

    def alert_callback(alert):
        callback_called.append(alert)

    async def async_alert_callback(alert):
        callback_called.append(f"async_{alert.id}")

    health_monitor.add_alert_callback(alert_callback)
    health_monitor.add_alert_callback(async_alert_callback)

    # Setup mock to fail
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=False,
        provider="test_provider",
        last_check=time.time(),
        error_message="Provider is down"
    )

    health_monitor.register_provider("test_provider", mock_provider)

    # Trigger alert
    await health_monitor.check_provider_health("test_provider")
    await health_monitor.check_provider_health("test_provider")

    # Should have called both callbacks
    assert len(callback_called) == 2
    assert isinstance(callback_called[0], HealthAlert)
    assert callback_called[1].startswith("async_")


@pytest.mark.asyncio
async def test_manual_alert_resolution(health_monitor):
    """Test manual alert resolution."""
    # Create a mock alert
    alert = HealthAlert(
        id="test_alert",
        timestamp=time.time(),
        provider="test_provider",
        severity=AlertSeverity.WARNING,
        message="Test alert"
    )
    health_monitor.active_alerts["test_key"] = alert

    # Resolve alert
    result = await health_monitor.resolve_alert("test_alert")
    assert result is False  # Alert ID not found in active_alerts keys

    # Try with correct key
    alert.id = "test_key"
    result = await health_monitor.resolve_alert("test_key")
    assert result is True
    assert alert.resolved is True
    assert alert.resolved_at is not None


@pytest.mark.asyncio
async def test_monitoring_lifecycle(health_monitor, mock_provider):
    """Test starting and stopping monitoring."""
    # Setup mock
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=True,
        provider="test_provider",
        last_check=time.time()
    )
    health_monitor.register_provider("test_provider", mock_provider)

    # Start monitoring
    await health_monitor.start_monitoring()
    assert health_monitor._monitoring_task is not None

    # Let it run briefly
    await asyncio.sleep(0.1)

    # Stop monitoring
    await health_monitor.stop_monitoring()
    assert health_monitor._monitoring_task is None


@pytest.mark.asyncio
async def test_context_manager(health_config, mock_provider):
    """Test health monitor as async context manager."""
    mock_provider.check_health.return_value = LLMHealthStatus(
        is_healthy=True,
        provider="test_provider",
        last_check=time.time()
    )

    async with HealthMonitor(health_config) as monitor:
        monitor.register_provider("test_provider", mock_provider)
        assert monitor._monitoring_task is not None

        # Let it run briefly
        await asyncio.sleep(0.1)

    # Should be stopped after context exit
    assert monitor._monitoring_task is None


@pytest.mark.asyncio
async def test_cleanup_old_data(health_monitor):
    """Test cleanup of old health check data."""
    # Add many health check results
    for i in range(150):
        result = HealthCheckResult(
            provider="test_provider",
            timestamp=time.time() - i,
            status=HealthStatus.HEALTHY,
            response_time=1.0
        )
        health_monitor.health_history.append(result)

    # Force cleanup
    health_monitor._last_cleanup = 0  # Force cleanup
    await health_monitor._cleanup_old_data()

    # Should be limited to max_history_size
    assert len(health_monitor.health_history) <= health_monitor.config.max_history_size


@pytest.mark.asyncio
async def test_concurrent_health_checks(health_monitor):
    """Test concurrent health checks don't interfere."""
    # Setup multiple providers
    providers = {}
    for i in range(5):
        provider = AsyncMock(spec=LLMProvider)
        provider.check_health.return_value = LLMHealthStatus(
            is_healthy=True,
            provider=f"provider_{i}",
            last_check=time.time()
        )
        providers[f"provider_{i}"] = provider
        health_monitor.register_provider(f"provider_{i}", provider)

    # Run concurrent health checks
    tasks = [
        health_monitor.check_provider_health(f"provider_{i}")
        for i in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # All should succeed
    assert len(results) == 5
    for result in results:
        assert result.status == HealthStatus.HEALTHY
