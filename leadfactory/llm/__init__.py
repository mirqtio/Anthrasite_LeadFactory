"""
LLM Package

This package provides a unified interface for Large Language Model providers
with fallback mechanisms, cost monitoring, and health checks.
"""

from .claude_provider import ClaudeProvider
from .cost_monitor import (
    AlertLevel,
    BudgetConfig,
    BudgetPeriod,
    CostMonitor,
    CostStats,
)
from .fallback_manager import (
    FallbackConfig,
    FallbackManager,
    FallbackStrategy,
)
from .gpt4o_provider import GPT4oProvider
from .health_monitor import (
    AlertSeverity,
    HealthAlert,
    HealthCheckResult,
    HealthConfig,
    HealthMonitor,
    HealthStatus,
    ProviderMetrics,
)
from .provider import (
    LLMError,
    LLMErrorType,
    LLMHealthStatus,
    LLMProvider,
    LLMResponse,
)

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMError",
    "LLMErrorType",
    "LLMHealthStatus",
    "GPT4oProvider",
    "ClaudeProvider",
    "FallbackManager",
    "FallbackStrategy",
    "FallbackConfig",
    "CostMonitor",
    "BudgetConfig",
    "BudgetPeriod",
    "AlertLevel",
    "CostStats",
    "HealthMonitor",
    "HealthConfig",
    "HealthStatus",
    "AlertSeverity",
    "HealthCheckResult",
    "ProviderMetrics",
    "HealthAlert",
]
