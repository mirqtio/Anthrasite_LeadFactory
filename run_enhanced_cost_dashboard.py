#!/usr/bin/env python3
"""
Enhanced Cost Dashboard Startup Script
======================================

This script starts the enhanced cost dashboard with all integrated features:
- Real-time cost monitoring via WebSockets
- Advanced analytics and forecasting
- Cost optimization recommendations
- Integration with existing LeadFactory infrastructure

Usage:
    python run_enhanced_cost_dashboard.py [--host HOST] [--port PORT] [--debug]

Features:
- Enhanced cost breakdown API (port 5001)
- Real-time WebSocket streaming
- Advanced analytics dashboard (port 5002)
- Integration with SQLite databases and Prometheus metrics
- Cost optimization recommendations
- Multi-format data export (JSON, CSV)
"""

import argparse
import logging
import sys
import threading
import time
from typing import Optional

# Import the enhanced cost dashboard components
from leadfactory.api.cost_metrics_integration import (
    start_integrated_cost_system,
    stop_integrated_cost_system,
)
from leadfactory.monitoring.enhanced_cost_dashboard import run_enhanced_dashboard
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhanced Cost Dashboard for LeadFactory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start dashboard with default settings
    python run_enhanced_cost_dashboard.py

    # Start dashboard on custom host/port
    python run_enhanced_cost_dashboard.py --host 0.0.0.0 --port 5003

    # Start dashboard in debug mode
    python run_enhanced_cost_dashboard.py --debug
        """,
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the dashboard to (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5002,
        help="Port to bind the dashboard to (default: 5002)",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    parser.add_argument(
        "--no-integration",
        action="store_true",
        help="Skip starting the cost metrics integration system",
    )

    return parser.parse_args()


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("enhanced_cost_dashboard.log"),
        ],
    )

    logger.info(f"Logging configured (level: {logging.getLevelName(level)})")


def start_integration_system():
    """Start the cost metrics integration system."""
    try:
        logger.info("Starting cost metrics integration system...")
        start_integrated_cost_system()

        # Give the integration system time to initialize
        time.sleep(2)

        logger.info("Cost metrics integration system started successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to start cost metrics integration system: {e}")
        return False


def stop_integration_system():
    """Stop the cost metrics integration system."""
    try:
        logger.info("Stopping cost metrics integration system...")
        stop_integrated_cost_system()
        logger.info("Cost metrics integration system stopped successfully")

    except Exception as e:
        logger.error(f"Error stopping cost metrics integration system: {e}")


def check_system_health():
    """Check if all required components are available."""
    health_checks = []

    try:
        # Check if cost tracking is available
        from leadfactory.cost.cost_tracking import cost_tracker

        daily_cost = cost_tracker.get_daily_cost()
        health_checks.append(("Cost Tracker", True, f"Daily cost: ${daily_cost:.2f}"))
    except Exception as e:
        health_checks.append(("Cost Tracker", False, str(e)))

    try:
        # Check if analytics engine is available
        from leadfactory.analytics.cost_analytics import cost_analytics_engine

        health_checks.append(("Analytics Engine", True, "Available"))
    except Exception as e:
        health_checks.append(("Analytics Engine", False, str(e)))

    try:
        # Check if Prometheus metrics are available
        from leadfactory.utils.metrics import METRICS_AVAILABLE

        health_checks.append(
            (
                "Prometheus Metrics",
                METRICS_AVAILABLE,
                "Available" if METRICS_AVAILABLE else "Not available",
            )
        )
    except Exception as e:
        health_checks.append(("Prometheus Metrics", False, str(e)))

    # Display health check results
    logger.info("System Health Check Results:")
    logger.info("=" * 50)

    all_healthy = True
    for component, healthy, message in health_checks:
        status = "✓" if healthy else "✗"
        level = logging.INFO if healthy else logging.WARNING
        logger.log(level, f"{status} {component:20} - {message}")
        if not healthy:
            all_healthy = False

    logger.info("=" * 50)

    if all_healthy:
        logger.info("All systems are healthy and ready!")
    else:
        logger.warning(
            "Some systems have issues. Dashboard will still function but with limited features."
        )

    return all_healthy


def print_startup_info(host: str, port: int):
    """Print startup information and URLs."""
    print("\n" + "=" * 70)
    print("🚀 Enhanced Cost Dashboard for LeadFactory")
    print("=" * 70)
    print(f"Dashboard URL:     http://{host}:{port}")
    print(f"API Endpoints:")
    print(f"  - Dashboard Data: http://{host}:{port}/api/enhanced/dashboard-data")
    print(f"  - Cost Trends:    http://{host}:{port}/api/enhanced/cost-trends")
    print(
        f"  - Optimization:   http://{host}:{port}/api/enhanced/optimization-recommendations"
    )
    print(f"  - Efficiency:     http://{host}:{port}/api/enhanced/cost-efficiency")
    print(f"  - Health Check:   http://{host}:{port}/api/enhanced/health")
    print(f"  - Export JSON:    http://{host}:{port}/api/enhanced/export/json")
    print(f"  - Export CSV:     http://{host}:{port}/api/enhanced/export/csv")
    print(f"\nCost Breakdown API: http://{host}:5001")
    print(f"  - Detailed Breakdown: http://{host}:5001/api/cost/breakdown")
    print(f"  - Real-time Stream:   WebSocket connection available")
    print("\nFeatures:")
    print("  ✓ Real-time cost monitoring")
    print("  ✓ Advanced trend analysis and forecasting")
    print("  ✓ Cost optimization recommendations")
    print("  ✓ Multi-service cost breakdown")
    print("  ✓ Integration with existing LeadFactory infrastructure")
    print("  ✓ WebSocket-based real-time updates")
    print("  ✓ Export capabilities (JSON, CSV)")
    print("=" * 70)
    print("Press Ctrl+C to stop the dashboard")
    print("=" * 70 + "\n")


def main():
    """Main entry point for the enhanced cost dashboard."""
    args = parse_arguments()

    # Setup logging
    setup_logging(args.debug)

    logger.info("Starting Enhanced Cost Dashboard for LeadFactory")
    logger.info(f"Arguments: host={args.host}, port={args.port}, debug={args.debug}")

    # Check system health
    health_status = check_system_health()

    integration_started = False

    try:
        # Start integration system if not disabled
        if not args.no_integration:
            integration_started = start_integration_system()
            if not integration_started:
                logger.warning(
                    "Integration system failed to start, continuing with limited functionality"
                )

        # Print startup information
        print_startup_info(args.host, args.port)

        # Start the enhanced dashboard
        logger.info(f"Starting enhanced cost dashboard on {args.host}:{args.port}")

        # Import and run the dashboard
        from leadfactory.monitoring.enhanced_cost_dashboard import EnhancedCostDashboard

        dashboard = EnhancedCostDashboard(
            host=args.host, port=args.port, debug=args.debug
        )

        dashboard.run()

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")

    except Exception as e:
        logger.error(f"Error starting enhanced cost dashboard: {e}")
        return 1

    finally:
        # Cleanup
        if integration_started:
            stop_integration_system()

        logger.info("Enhanced cost dashboard shutdown complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
