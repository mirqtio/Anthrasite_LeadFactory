"""
Monitoring and Analytics Module
=============================

This module provides comprehensive monitoring, alerting, and analytics
capabilities for the LeadFactory platform, including:

1. Purchase metrics and business intelligence
2. CI Pipeline Test Monitoring and Governance Framework (Task 14)
   - Advanced test monitoring dashboard
   - Intelligent alerting and notification system
   - Test governance framework with ownership tracking
   - Long-term analytics and prediction system
   - Development workflow integration
"""

# Purchase monitoring (existing)
from .alert_manager import AlertManager, alert_manager
from .conversion_tracking import ConversionTracker, conversion_tracker
from .metrics_aggregator import MetricsAggregator, metrics_aggregator
from .purchase_monitoring import PurchaseMonitor, purchase_monitor

# Test monitoring framework (Task 14)
try:
    from .test_alerting import Alert, AlertRule, start_alert_monitoring
    from .test_alerting import AlertManager as TestAlertManager
    from .test_alerting import alert_manager as test_alert_manager
    from .test_analytics import (
        CorrelationAnalysis,
        PredictionResult,
        TestAnalyticsEngine,
        TrendAnalysis,
        analytics_engine,
        generate_weekly_analytics_report,
        predict_instability,
    )
    from .test_dashboard import run_dashboard
    from .test_governance import (
        TestGovernanceManager,
        TestModificationRequest,
        TestOwnershipInfo,
        assign_test_owner,
        governance_manager,
        request_test_disable,
    )
    from .test_monitoring import (
        TestExecution,
        TestMetrics,
        TestMetricsCollector,
        TestSuiteMetrics,
        get_test_health_report,
        metrics_collector,
        record_test_result,
    )
    from .workflow_integration import (
        GitHubIssue,
        PullRequestCheck,
        WorkflowIntegrationManager,
        check_pr_test_health,
        create_test_issue_for_alert,
        workflow_manager,
    )

    TEST_MONITORING_AVAILABLE = True

except ImportError:
    TEST_MONITORING_AVAILABLE = False
    # Test monitoring dependencies not available

__all__ = [
    # Purchase monitoring
    "PurchaseMonitor",
    "purchase_monitor",
    "MetricsAggregator",
    "metrics_aggregator",
    "AlertManager",
    "alert_manager",
    "ConversionTracker",
    "conversion_tracker",
]

# Add test monitoring exports if available
if TEST_MONITORING_AVAILABLE:
    __all__.extend(
        [
            # Core test monitoring
            "TestExecution",
            "TestMetrics",
            "TestSuiteMetrics",
            "TestMetricsCollector",
            "metrics_collector",
            "record_test_result",
            "get_test_health_report",
            # Dashboard
            "run_dashboard",
            # Test alerting
            "Alert",
            "AlertRule",
            "TestAlertManager",
            "test_alert_manager",
            "start_alert_monitoring",
            # Governance
            "TestOwnershipInfo",
            "TestModificationRequest",
            "TestGovernanceManager",
            "governance_manager",
            "assign_test_owner",
            "request_test_disable",
            # Analytics
            "PredictionResult",
            "CorrelationAnalysis",
            "TrendAnalysis",
            "TestAnalyticsEngine",
            "analytics_engine",
            "predict_instability",
            "generate_weekly_analytics_report",
            # Workflow Integration
            "GitHubIssue",
            "PullRequestCheck",
            "WorkflowIntegrationManager",
            "workflow_manager",
            "create_test_issue_for_alert",
            "check_pr_test_health",
        ]
    )
