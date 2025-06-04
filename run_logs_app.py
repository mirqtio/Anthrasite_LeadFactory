#!/usr/bin/env python3
"""
Launch the Logs Browser Web Application.

This script starts the Flask web application that provides the logs browsing interface
for HTML and LLM logs. It serves both the API endpoints and the static frontend.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from leadfactory.api.logs_api import create_logs_app
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point for the logs browser application."""
    try:
        # Create the Flask application
        app = create_logs_app()

        # Add route to serve the static logs.html file
        @app.route("/logs")
        def logs_browser():
            """Serve the logs browser interface."""
            logs_html_path = project_root / "leadfactory" / "static" / "logs.html"
            if logs_html_path.exists():
                with open(logs_html_path, encoding="utf-8") as f:
                    return f.read()
            else:
                return "Logs browser interface not found", 404

        # Add route to serve the dashboard.html file
        @app.route("/dashboard")
        def dashboard():
            """Serve the analytics dashboard interface."""
            dashboard_html_path = (
                project_root / "leadfactory" / "static" / "dashboard.html"
            )
            if dashboard_html_path.exists():
                with open(dashboard_html_path, encoding="utf-8") as f:
                    return f.read()
            else:
                return "Dashboard interface not found", 404

        # Configuration
        host = os.getenv("LOGS_HOST", "127.0.0.1")  # nosec B104
        port = int(os.getenv("LOGS_PORT", "5000"))
        debug = os.getenv("LOGS_DEBUG", "False").lower() == "true"

        logger.info("Starting Logs Browser Application")
        logger.info(f"API endpoints available at: http://{host}:{port}/api/")
        logger.info(f"Web interface available at: http://{host}:{port}/logs")
        logger.info(f"Health check available at: http://{host}:{port}/api/health")

        # Start the Flask development server
        app.run(host=host, port=port, debug=debug, threaded=True)  # nosec

    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
