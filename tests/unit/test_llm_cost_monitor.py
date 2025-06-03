"""
Tests for LLM Cost Monitoring System
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from leadfactory.llm.cost_monitor import (
    CostMonitor,
    BudgetConfig,
    BudgetPeriod,
    AlertLevel,
    CostEntry,
    CostStats
)


@pytest.fixture
def event_loop():
    """Create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def budget_config():
    """Create a test budget configuration."""
    return BudgetConfig(
        daily_limit=10.0,
        weekly_limit=50.0,
        monthly_limit=200.0,
        warning_threshold=0.8,
        critical_threshold=0.95,
        enable_auto_pause=True
    )


@pytest.fixture
def cost_monitor(budget_config):
    """Create a cost monitor instance."""
    return CostMonitor(budget_config)


@pytest.mark.asyncio
async def test_cost_monitor_initialization(budget_config):
    """Test cost monitor initialization."""
    monitor = CostMonitor(budget_config)

    assert monitor.config == budget_config
    assert monitor.cost_entries == []
    assert monitor._alert_callbacks == []


@pytest.mark.asyncio
async def test_record_cost_basic(cost_monitor):
    """Test basic cost recording."""
    await cost_monitor.record_cost(
        provider="gpt4o",
        cost=1.50,
        tokens_used=1000,
        request_type="completion",
        model="gpt-4o",
        prompt_tokens=800,
        completion_tokens=200
    )

    assert len(cost_monitor.cost_entries) == 1
    entry = cost_monitor.cost_entries[0]

    assert entry.provider == "gpt4o"
    assert entry.cost == 1.50
    assert entry.tokens_used == 1000
    assert entry.request_type == "completion"
    assert entry.model == "gpt-4o"
    assert entry.prompt_tokens == 800
    assert entry.completion_tokens == 200


@pytest.mark.asyncio
async def test_record_multiple_costs(cost_monitor):
    """Test recording multiple cost entries."""
    costs = [
        ("gpt4o", 1.50, 1000),
        ("claude", 1.20, 800),
        ("gpt4o", 2.00, 1200)
    ]

    for provider, cost, tokens in costs:
        await cost_monitor.record_cost(
            provider=provider,
            cost=cost,
            tokens_used=tokens
        )

    assert len(cost_monitor.cost_entries) == 3

    # Check total costs
    total_cost = sum(entry.cost for entry in cost_monitor.cost_entries)
    assert total_cost == 4.70


@pytest.mark.asyncio
async def test_get_current_costs_daily(cost_monitor):
    """Test getting current costs for daily period."""
    # Record some costs
    await cost_monitor.record_cost("gpt4o", 2.50, 1000)
    await cost_monitor.record_cost("claude", 1.80, 800)

    stats = await cost_monitor.get_current_costs(BudgetPeriod.DAILY)

    assert stats.period == BudgetPeriod.DAILY
    assert stats.total_cost == 4.30
    assert stats.total_requests == 2
    assert stats.total_tokens == 1800
    assert stats.provider_costs["gpt4o"] == 2.50
    assert stats.provider_costs["claude"] == 1.80
    assert stats.average_cost_per_request == 2.15
    assert abs(stats.average_cost_per_token - 0.00239) < 0.0001


@pytest.mark.asyncio
async def test_get_current_costs_provider_filter(cost_monitor):
    """Test getting costs filtered by provider."""
    await cost_monitor.record_cost("gpt4o", 2.50, 1000)
    await cost_monitor.record_cost("claude", 1.80, 800)
    await cost_monitor.record_cost("gpt4o", 1.20, 600)

    # Get stats for gpt4o only
    stats = await cost_monitor.get_current_costs(
        BudgetPeriod.DAILY,
        provider="gpt4o"
    )

    assert stats.total_cost == 3.70  # 2.50 + 1.20
    assert stats.total_requests == 2
    assert stats.total_tokens == 1600
    assert "claude" not in stats.provider_costs


@pytest.mark.asyncio
async def test_check_budget_status_normal(cost_monitor):
    """Test budget status check under normal conditions."""
    await cost_monitor.record_cost("gpt4o", 2.00, 1000)

    status = await cost_monitor.check_budget_status(BudgetPeriod.DAILY)

    assert status["period"] == "daily"
    assert status["limit"] == 10.0
    assert status["current_cost"] == 2.00
    assert status["remaining_budget"] == 8.00
    assert status["usage_percentage"] == 20.0
    assert status["alert_level"] == "info"
    assert status["should_pause"] is False


@pytest.mark.asyncio
async def test_check_budget_status_warning(cost_monitor):
    """Test budget status check at warning threshold."""
    # Record cost that exceeds warning threshold (80% of 10.0 = 8.0)
    await cost_monitor.record_cost("gpt4o", 8.50, 1000)

    status = await cost_monitor.check_budget_status(BudgetPeriod.DAILY)

    assert status["usage_percentage"] == 85.0
    assert status["alert_level"] == "warning"
    assert status["should_pause"] is False


@pytest.mark.asyncio
async def test_check_budget_status_critical(cost_monitor):
    """Test budget status check at critical threshold."""
    # Record cost that exceeds critical threshold (95% of 10.0 = 9.5)
    await cost_monitor.record_cost("gpt4o", 9.80, 1000)

    status = await cost_monitor.check_budget_status(BudgetPeriod.DAILY)

    assert status["usage_percentage"] == 98.0
    assert status["alert_level"] == "critical"
    assert status["should_pause"] is False


@pytest.mark.asyncio
async def test_check_budget_status_exceeded(cost_monitor):
    """Test budget status check when budget is exceeded."""
    # Record cost that exceeds daily limit (10.0)
    await cost_monitor.record_cost("gpt4o", 12.00, 1000)

    status = await cost_monitor.check_budget_status(BudgetPeriod.DAILY)

    assert status["usage_percentage"] == 120.0
    assert status["alert_level"] == "emergency"
    assert status["should_pause"] is True
    assert status["remaining_budget"] == 0


@pytest.mark.asyncio
async def test_is_budget_exceeded(cost_monitor):
    """Test budget exceeded check."""
    # Normal usage
    await cost_monitor.record_cost("gpt4o", 5.00, 1000)
    assert await cost_monitor.is_budget_exceeded() is False

    # Exceeded usage
    await cost_monitor.record_cost("gpt4o", 6.00, 1000)  # Total: 11.00
    assert await cost_monitor.is_budget_exceeded() is True


@pytest.mark.asyncio
async def test_get_cheapest_provider(cost_monitor):
    """Test getting the cheapest provider."""
    # Record different costs for providers
    await cost_monitor.record_cost("gpt4o", 3.00, 1000)  # $0.003 per token
    await cost_monitor.record_cost("claude", 2.00, 1000)  # $0.002 per token
    await cost_monitor.record_cost("gpt4o", 1.50, 500)   # Average: $0.0025 per token

    cheapest = await cost_monitor.get_cheapest_provider(
        ["gpt4o", "claude"],
        BudgetPeriod.DAILY
    )

    assert cheapest == "claude"


@pytest.mark.asyncio
async def test_get_cheapest_provider_no_data(cost_monitor):
    """Test getting cheapest provider with no data."""
    cheapest = await cost_monitor.get_cheapest_provider(
        ["gpt4o", "claude"],
        BudgetPeriod.DAILY
    )

    assert cheapest is None


@pytest.mark.asyncio
async def test_alert_callbacks(cost_monitor):
    """Test alert callback functionality."""
    callback_calls = []

    async def test_callback(period, status):
        callback_calls.append((period, status))

    cost_monitor.add_alert_callback(test_callback)

    # Record cost that triggers warning
    await cost_monitor.record_cost("gpt4o", 8.50, 1000)

    # Give some time for async processing
    await asyncio.sleep(0.1)

    assert len(callback_calls) == 1
    period, status = callback_calls[0]
    assert period == BudgetPeriod.DAILY
    assert status["alert_level"] == "warning"


@pytest.mark.asyncio
async def test_export_cost_data_json(cost_monitor):
    """Test exporting cost data in JSON format."""
    # Record some test data
    await cost_monitor.record_cost("gpt4o", 2.50, 1000, model="gpt-4o")
    await cost_monitor.record_cost("claude", 1.80, 800, model="claude-3")

    data = await cost_monitor.export_cost_data(format="json")

    assert "entries" in data
    assert len(data["entries"]) == 2
    assert data["total_entries"] == 2

    # Check first entry
    entry = data["entries"][0]
    assert entry["provider"] == "gpt4o"
    assert entry["cost"] == 2.50
    assert entry["tokens_used"] == 1000
    assert entry["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_export_cost_data_csv(cost_monitor):
    """Test exporting cost data in CSV format."""
    await cost_monitor.record_cost("gpt4o", 2.50, 1000)

    csv_data = await cost_monitor.export_cost_data(format="csv")

    assert isinstance(csv_data, str)
    assert "provider,timestamp,cost,tokens_used" in csv_data
    assert "gpt4o" in csv_data
    assert "2.5" in csv_data


@pytest.mark.asyncio
async def test_export_cost_data_invalid_format(cost_monitor):
    """Test exporting with invalid format."""
    with pytest.raises(ValueError, match="Unsupported format"):
        await cost_monitor.export_cost_data(format="xml")


@pytest.mark.asyncio
async def test_period_limits(cost_monitor):
    """Test different budget period limits."""
    # Test daily limit
    status = await cost_monitor.check_budget_status(BudgetPeriod.DAILY)
    assert status["limit"] == 10.0

    # Test weekly limit
    status = await cost_monitor.check_budget_status(BudgetPeriod.WEEKLY)
    assert status["limit"] == 50.0

    # Test monthly limit
    status = await cost_monitor.check_budget_status(BudgetPeriod.MONTHLY)
    assert status["limit"] == 200.0


@pytest.mark.asyncio
async def test_cost_entry_with_metadata(cost_monitor):
    """Test recording cost entry with metadata."""
    metadata = {
        "user_id": "test_user",
        "session_id": "session_123",
        "feature": "mockup_generation"
    }

    await cost_monitor.record_cost(
        provider="gpt4o",
        cost=1.50,
        tokens_used=1000,
        metadata=metadata
    )

    entry = cost_monitor.cost_entries[0]
    assert entry.metadata == metadata


@pytest.mark.asyncio
async def test_concurrent_cost_recording(cost_monitor):
    """Test concurrent cost recording with async lock."""
    async def record_cost_batch(provider, start_cost):
        for i in range(10):
            await cost_monitor.record_cost(
                provider=provider,
                cost=start_cost + i * 0.1,
                tokens_used=100
            )

    # Record costs concurrently
    await asyncio.gather(
        record_cost_batch("gpt4o", 1.0),
        record_cost_batch("claude", 2.0)
    )

    assert len(cost_monitor.cost_entries) == 20

    # Verify total costs
    gpt4o_costs = [e.cost for e in cost_monitor.cost_entries if e.provider == "gpt4o"]
    claude_costs = [e.cost for e in cost_monitor.cost_entries if e.provider == "claude"]

    assert len(gpt4o_costs) == 10
    assert len(claude_costs) == 10


@pytest.mark.asyncio
async def test_cleanup_old_entries(cost_monitor):
    """Test cleanup of old cost entries."""
    # Mock old timestamp (31 days ago)
    old_timestamp = time.time() - (31 * 24 * 3600)

    # Add old entry manually
    old_entry = CostEntry(
        provider="gpt4o",
        timestamp=old_timestamp,
        cost=1.0,
        tokens_used=100,
        request_type="completion",
        model="gpt-4o"
    )
    cost_monitor.cost_entries.append(old_entry)

    # Add recent entry
    await cost_monitor.record_cost("gpt4o", 2.0, 200)

    assert len(cost_monitor.cost_entries) == 2

    # Force cleanup by setting last cleanup time to old value
    cost_monitor._last_cleanup = 0
    await cost_monitor._cleanup_old_entries()

    # Old entry should be removed
    assert len(cost_monitor.cost_entries) == 1
    assert cost_monitor.cost_entries[0].cost == 2.0


if __name__ == "__main__":
    pytest.main([__file__])
