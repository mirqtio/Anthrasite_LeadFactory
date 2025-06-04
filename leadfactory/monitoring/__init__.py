"""
Monitoring and Analytics Module
=============================

This module provides comprehensive monitoring, alerting, and analytics
capabilities for the LeadFactory platform, with a focus on purchase
metrics and business intelligence.
"""

from .alert_manager import AlertManager, alert_manager
from .conversion_tracking import ConversionTracker, conversion_tracker
from .metrics_aggregator import MetricsAggregator, metrics_aggregator
from .purchase_monitoring import PurchaseMonitor, purchase_monitor

__all__ = [
    "PurchaseMonitor",
    "purchase_monitor",
    "MetricsAggregator",
    "metrics_aggregator",
    "AlertManager",
    "alert_manager",
    "ConversionTracker",
    "conversion_tracker",
]
