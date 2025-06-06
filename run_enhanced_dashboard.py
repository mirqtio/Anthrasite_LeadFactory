#!/usr/bin/env python3
"""
Enhanced Cost Dashboard Startup Script
=====================================

This script starts the enhanced cost dashboard for LeadFactory with comprehensive
cost analytics and real-time monitoring capabilities.

Usage:
    python run_enhanced_dashboard.py [--host HOST] [--port PORT] [--debug]

Examples:
    python run_enhanced_dashboard.py
    python run_enhanced_dashboard.py --host 0.0.0.0 --port 5002
    python run_enhanced_dashboard.py --debug
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from leadfactory.monitoring.enhanced_dashboard import run_enhanced_dashboard
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


def validate_environment():
    """Validate that the environment is properly set up."""
    try:
        # Check if cost tracking is available
        from leadfactory.cost.cost_tracking import cost_tracker

        logger.info("✅ Cost tracking system available")

        # Check if cost aggregation is available
        from leadfactory.cost.cost_aggregation import cost_aggregation_service

        logger.info("✅ Cost aggregation service available")

        # Check if financial tracking is available
        from leadfactory.cost.financial_tracking import financial_tracker

        logger.info("✅ Financial tracking available")

        return True

    except ImportError as e:
        logger.error(f"❌ Missing required dependency: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Environment validation failed: {e}")
        return False


def main():
    """Main entry point for the enhanced dashboard."""
    parser = argparse.ArgumentParser(
        description="Enhanced Cost Dashboard for LeadFactory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Start on localhost:5001
  %(prog)s --host 0.0.0.0           # Bind to all interfaces
  %(prog)s --port 5002              # Use custom port
  %(prog)s --debug                  # Enable debug mode
        """,
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the dashboard to (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to bind the dashboard to (default: 5001)",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    logger.info("=" * 60)
    logger.info("Enhanced Cost Dashboard for LeadFactory")
    logger.info("=" * 60)

    # Validate environment
    logger.info("Validating environment...")
    if not validate_environment():
        logger.error("Environment validation failed. Please check your setup.")
        sys.exit(1)

    logger.info("Environment validation successful!")

    # Start the dashboard
    try:
        logger.info(f"Starting enhanced cost dashboard...")
        logger.info(f"Host: {args.host}")
        logger.info(f"Port: {args.port}")
        logger.info(f"Debug: {args.debug}")
        logger.info(f"Dashboard URL: http://{args.host}:{args.port}/enhanced-dashboard")
        logger.info("=" * 60)

        # Run the dashboard
        run_enhanced_dashboard(host=args.host, port=args.port, debug=args.debug)

    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
