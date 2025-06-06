"""
Main Flask web application for LeadFactory.

This module provides a Flask-based web application that serves:
- API endpoints for business management, handoff queue, and other services
- Static web interfaces for bulk qualification and handoff queue management
- Integration with existing LeadFactory services
"""

import os
from datetime import datetime

from flask import Flask, jsonify, render_template_string, send_from_directory
from flask_cors import CORS

from leadfactory.api.business_management_api import business_management
from leadfactory.api.error_management_api import error_management
from leadfactory.api.handoff_queue_api import handoff_queue
from leadfactory.api.logs_api import logs_api
from leadfactory.api.mockup_qa_api import mockup_qa
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


def create_app(config=None):
    """Create and configure the Flask application.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured Flask application
    """
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # Configure CORS
    CORS(app, origins=["*"])

    # Basic configuration
    app.config.update(
        {
            "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-secret-key"),
            "JSON_SORT_KEYS": False,
            "JSONIFY_PRETTYPRINT_REGULAR": True,
        }
    )

    if config:
        app.config.update(config)

    # Register API blueprints
    app.register_blueprint(business_management, url_prefix="")
    app.register_blueprint(handoff_queue, url_prefix="")
    app.register_blueprint(logs_api, url_prefix="")
    app.register_blueprint(error_management, url_prefix="")
    app.register_blueprint(mockup_qa, url_prefix="")

    # Health check endpoint
    @app.route("/health")
    def health_check():
        """Health check endpoint."""
        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "leadfactory-web",
            }
        )

    # Root route with navigation
    @app.route("/")
    def index():
        """Main landing page with navigation to different interfaces."""
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LeadFactory Management Portal</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }

                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                }

                .container {
                    text-align: center;
                    max-width: 800px;
                    padding: 40px;
                }

                .logo {
                    font-size: 3rem;
                    font-weight: 700;
                    margin-bottom: 20px;
                    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
                }

                .subtitle {
                    font-size: 1.2rem;
                    margin-bottom: 40px;
                    opacity: 0.9;
                }

                .nav-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-top: 40px;
                }

                .nav-card {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    border-radius: 16px;
                    padding: 30px;
                    text-decoration: none;
                    color: white;
                    transition: all 0.3s ease;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                }

                .nav-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                    background: rgba(255, 255, 255, 0.15);
                }

                .nav-card h3 {
                    font-size: 1.5rem;
                    margin-bottom: 15px;
                    font-weight: 600;
                }

                .nav-card p {
                    opacity: 0.8;
                    line-height: 1.5;
                }

                .api-docs {
                    margin-top: 40px;
                    padding-top: 40px;
                    border-top: 1px solid rgba(255, 255, 255, 0.2);
                }

                .api-docs h3 {
                    margin-bottom: 20px;
                    font-size: 1.3rem;
                }

                .api-endpoints {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    text-align: left;
                }

                .api-endpoint {
                    background: rgba(255, 255, 255, 0.1);
                    padding: 15px;
                    border-radius: 8px;
                    font-family: monospace;
                    font-size: 0.9rem;
                }

                .method {
                    font-weight: bold;
                    color: #4ade80;
                }

                .method.post {
                    color: #fbbf24;
                }

                .method.get {
                    color: #60a5fa;
                }

                @media (max-width: 768px) {
                    .container {
                        padding: 20px;
                    }

                    .logo {
                        font-size: 2rem;
                    }

                    .nav-grid {
                        grid-template-columns: 1fr;
                    }

                    .api-endpoints {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">LeadFactory</div>
                <div class="subtitle">Lead Generation & Sales Management Portal</div>

                <div class="nav-grid">
                    <a href="/static/bulk_qualification.html" class="nav-card">
                        <h3>Bulk Qualification</h3>
                        <p>Select and qualify multiple leads for handoff to sales team using configurable criteria</p>
                    </a>

                    <a href="/static/handoff_queue.html" class="nav-card">
                        <h3>Handoff Queue</h3>
                        <p>Manage qualified leads, assign to sales team members, and track progress</p>
                    </a>

                    <a href="/static/logs.html" class="nav-card">
                        <h3>System Logs</h3>
                        <p>Browse and search system logs, monitor pipeline execution and errors</p>
                    </a>

                    <a href="/static/dashboard.html" class="nav-card">
                        <h3>Analytics Dashboard</h3>
                        <p>View comprehensive analytics, cost metrics, and performance insights</p>
                    </a>

                    <a href="/static/error_management.html" class="nav-card">
                        <h3>Error Management</h3>
                        <p>Monitor and manage pipeline errors, apply bulk fixes and dismiss issues</p>
                    </a>

                    <a href="/static/mockup_qa_modal.html" class="nav-card">
                        <h3>Mockup QA</h3>
                        <p>Review and approve mockup designs with quality assurance workflows</p>
                    </a>
                </div>

                <div class="api-docs">
                    <h3>API Endpoints</h3>
                    <div class="api-endpoints">
                        <div class="api-endpoint">
                            <span class="method post">POST</span> /api/handoff/qualify-bulk
                        </div>
                        <div class="api-endpoint">
                            <span class="method post">POST</span> /api/handoff/assign-bulk
                        </div>
                        <div class="api-endpoint">
                            <span class="method get">GET</span> /api/handoff/queue
                        </div>
                        <div class="api-endpoint">
                            <span class="method get">GET</span> /api/handoff/criteria
                        </div>
                        <div class="api-endpoint">
                            <span class="method get">GET</span> /api/handoff/sales-team
                        </div>
                        <div class="api-endpoint">
                            <span class="method get">GET</span> /api/handoff/analytics/summary
                        </div>
                        <div class="api-endpoint">
                            <span class="method post">POST</span> /api/businesses/bulk-reject
                        </div>
                        <div class="api-endpoint">
                            <span class="method get">GET</span> /api/businesses
                        </div>
                        <div class="api-endpoint">
                            <span class="method get">GET</span> /health
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return render_template_string(html_template)

    # Static file serving
    @app.route("/static/<path:filename>")
    def static_files(filename):
        """Serve static files."""
        return send_from_directory(app.static_folder, filename)

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return (
            jsonify(
                {
                    "error": "Not found",
                    "message": "The requested resource was not found",
                    "status_code": 404,
                }
            ),
            404,
        )

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {error}")
        return (
            jsonify(
                {
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "status_code": 500,
                }
            ),
            500,
        )

    logger.info("Flask application created successfully")
    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    """Run the Flask application directly."""
    import sys

    # Parse command line arguments
    port = 5000
    debug = False

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}")
            sys.exit(1)

    if len(sys.argv) > 2 and sys.argv[2].lower() in ("true", "debug", "1"):
        debug = True

    print(f"Starting LeadFactory web application on port {port}")
    print(f"Debug mode: {debug}")
    print(f"Visit http://localhost:{port} to access the application")

    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
