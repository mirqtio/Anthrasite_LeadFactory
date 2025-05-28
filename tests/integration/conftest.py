"""
Configuration and fixtures specifically for integration tests.

This module provides configuration and fixtures for toggling between real API calls and mocks
during integration testing. It implements command-line options and environment variables to
control test behavior.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime

import pytest
from _pytest.config import Config
from _pytest.terminal import TerminalReporter

# Import project modules
# Handle missing metrics module gracefully
try:
    from leadfactory.utils.metrics import COST_COUNTER, API_LATENCY
except (ImportError, ModuleNotFoundError):
    # Create mock metrics objects if the real ones aren't available
    class MockMetric:
        def __init__(self, name, description=None, labels=None):
            self.name = name
            self.description = description or name
            self.labels_schema = labels or []

        def labels(self, *args, **kwargs):
            return self

        def inc(self, value=1):
            pass

        def observe(self, value):
            pass

    # Create mock metric instances
    COST_COUNTER = MockMetric('api_cost_total', 'Total API cost in USD', ['api_name', 'operation'])
    API_LATENCY = MockMetric('api_latency_seconds', 'API latency in seconds', ['api_name', 'endpoint', 'status'])

# Import API fixtures to make them available to tests
from tests.integration.api_fixtures import (
    yelp_api,
    google_places_api,
    openai_api,
    sendgrid_api,
    screenshotone_api,
    setup_mock_data_dir,
)

# Import API test configuration
from tests.integration.api_test_config import APITestConfig

# Import API metrics fixtures
from tests.integration.api_metrics_fixture import (
    APIMetricsLogger,
    api_metrics_logger,
    api_metric_decorator,
    calculate_openai_cost
)

# Re-export the fixtures to make them available to all integration tests
__all__ = [
    'yelp_api',
    'google_places_api',
    'openai_api',
    'sendgrid_api',
    'screenshotone_api',
    'setup_mock_data_dir',
    'api_metrics_logger',
    'api_metric_decorator',
    'api_test_config',
    'metrics_report'
]


def pytest_addoption(parser):
    """Add command-line options for controlling API test behavior."""
    group = parser.getgroup("api_testing", "API Testing Options")
    group.addoption(
        "--use-real-apis",
        action="store_true",
        dest="use_real_apis",
        default=False,
        help="Use real APIs instead of mocks for integration tests"
    )
    group.addoption(
        "--apis",
        action="store",
        dest="apis",
        default="all",
        help="Comma-separated list of APIs to test with real calls (yelp,google,openai,sendgrid,screenshotone)"
    )
    group.addoption(
        "--log-metrics",
        action="store_true",
        dest="log_metrics",
        default=False,
        help="Log API metrics to file"
    )
    group.addoption(
        "--metrics-dir",
        action="store",
        dest="metrics_dir",
        default="metrics",
        help="Directory to store metrics data"
    )
    group.addoption(
        "--generate-report",
        action="store_true",
        dest="generate_report",
        default=False,
        help="Generate API metrics report after tests complete"
    )
    group.addoption(
        "--throttle-apis",
        action="store_true",
        dest="throttle_apis",
        default=False,
        help="Enable API throttling to respect rate limits"
    )


def pytest_configure(config: Config):
    """Configure the test environment based on options."""
    # Register markers
    config.addinivalue_line("markers", "real_api: mark test to run with real APIs")
    config.addinivalue_line("markers", "mock_only: mark test to run only with mocks")
    config.addinivalue_line("markers", "pipeline: mark test as a pipeline integration test")
    config.addinivalue_line("markers", "api_metrics: mark test for API metrics collection")

    # Set environment variable based on command line option
    if config.getoption("use_real_apis"):
        os.environ["LEADFACTORY_USE_REAL_APIS"] = "1"
    else:
        os.environ["LEADFACTORY_USE_REAL_APIS"] = "0"

    # Configure which APIs to test
    apis_to_test = config.getoption("apis").lower().split(",")
    if apis_to_test == ["all"]:
        # Set LEADFACTORY_TEST_APIS environment variable to "all"
        os.environ["LEADFACTORY_TEST_APIS"] = "all"
    else:
        # Set LEADFACTORY_TEST_APIS to the comma-separated list
        os.environ["LEADFACTORY_TEST_APIS"] = ",".join(apis_to_test)

    # Set API-specific environment variables for backward compatibility
    supported_apis = APITestConfig.get_config()["api_configs"].keys()
    for api in supported_apis:
        env_var = f"LEADFACTORY_TEST_{api.upper()}_API"
        if api in apis_to_test or "all" in apis_to_test:
            os.environ[env_var] = "1"
        else:
            os.environ[env_var] = "0"

    # Configure metrics logging
    if config.getoption("log_metrics"):
        os.environ["LEADFACTORY_LOG_API_METRICS"] = "1"
    else:
        os.environ["LEADFACTORY_LOG_API_METRICS"] = "0"

    # Configure metrics directory
    metrics_dir = config.getoption("metrics_dir")
    os.environ["METRICS_DIR"] = metrics_dir

    # Configure API throttling
    if config.getoption("throttle_apis"):
        for api in supported_apis:
            os.environ[f"LEADFACTORY_THROTTLE_{api.upper()}_API"] = "1"

    # Save the current configuration
    config.api_test_config = APITestConfig.get_config()

    # Create metrics directory if it doesn't exist
    Path(metrics_dir).mkdir(parents=True, exist_ok=True)


def pytest_collection_modifyitems(config: Config, items):
    """Skip tests based on the API configuration."""
    use_real_apis = config.getoption("use_real_apis")
    skip_real_api = pytest.mark.skip(reason="Test requires real API connection")
    skip_mock_only = pytest.mark.skip(reason="Test only works with mocks")

    for item in items:
        # Skip real_api tests when not using real APIs
        if "real_api" in item.keywords and not use_real_apis:
            item.add_marker(skip_real_api)
        # Skip mock_only tests when using real APIs
        elif "mock_only" in item.keywords and use_real_apis:
            item.add_marker(skip_mock_only)


@pytest.fixture
def use_real_apis(request):
    """Return whether tests should use real APIs."""
    return request.config.getoption("use_real_apis")


@pytest.fixture
def apis_to_test(request):
    """Return which APIs to test with real calls."""
    apis = request.config.getoption("apis").lower().split(",")
    return apis


@pytest.fixture
def api_keys() -> Dict[str, Optional[str]]:
    """Return API keys from environment variables."""
    return {
        "yelp": os.environ.get("YELP_API_KEY"),
        "google": os.environ.get("GOOGLE_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "sendgrid": os.environ.get("SENDGRID_API_KEY"),
        "screenshotone": os.environ.get("SCREENSHOTONE_API_KEY"),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
    }


@pytest.fixture(scope="session")
def api_test_config():
    """Return the API test configuration."""
    return APITestConfig.get_config()


@pytest.fixture(scope="session")
def metrics_report(api_metrics_logger):
    """Return a function to generate metrics reports."""
    def _generate_report(output_dir=None, format="json"):
        """Generate an API metrics report.

        Args:
            output_dir: Directory to save the report (default: METRICS_DIR)
            format: Report format ('json', 'csv', or 'html')

        Returns:
            Path to the generated report file
        """
        if output_dir is None:
            output_dir = Path(APITestConfig.metrics_directory())
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate appropriate report based on format
        if format == "json":
            report_path = output_dir / f"api_metrics_report_{timestamp}.json"
            with open(report_path, "w") as f:
                # Get aggregated metrics per API
                report_data = {
                    "apis": {},
                    "summary": api_metrics_logger.get_summary_stats(),
                    "timestamp": timestamp,
                    "config": APITestConfig.get_config()
                }

                for api in api_metrics_logger.get_all_apis():
                    report_data["apis"][api] = {
                        "metrics": api_metrics_logger.get_metrics_for_api(api),
                        "stats": api_metrics_logger.get_api_stats(api)
                    }

                import json
                json.dump(report_data, f, indent=2)

        elif format == "csv":
            report_path = output_dir / f"api_metrics_report_{timestamp}.csv"
            import pandas as pd

            # Convert metrics to DataFrame
            metrics_df = pd.DataFrame(api_metrics_logger.metrics)
            metrics_df.to_csv(report_path, index=False)

        elif format == "html":
            report_path = output_dir / f"api_metrics_report_{timestamp}.html"

            try:
                import pandas as pd
                import matplotlib.pyplot as plt
                import base64
                from io import BytesIO

                # Convert metrics to DataFrame
                metrics_df = pd.DataFrame(api_metrics_logger.metrics)

                # Generate plots
                plt.figure(figsize=(10, 6))

                # Plot 1: API Call Distribution
                api_counts = metrics_df['api'].value_counts()
                ax1 = plt.subplot(121)
                api_counts.plot(kind='bar', ax=ax1)
                plt.title('API Call Distribution')
                plt.ylabel('Number of Calls')
                plt.tight_layout()

                # Plot 2: Average Response Times
                ax2 = plt.subplot(122)
                avg_times = metrics_df.groupby('api')['request_time'].mean() * 1000  # Convert to ms
                avg_times.plot(kind='bar', ax=ax2)
                plt.title('Average Response Times')
                plt.ylabel('Time (ms)')
                plt.tight_layout()

                # Save plot to base64 string
                buffer = BytesIO()
                plt.savefig(buffer, format='png')
                plt.close()
                buffer.seek(0)
                plot_data = base64.b64encode(buffer.read()).decode('utf-8')

                # Generate HTML report
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>API Metrics Report - {timestamp}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        h1, h2, h3 {{ color: #333; }}
                        table {{ border-collapse: collapse; width: 100%; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                        th {{ background-color: #f2f2f2; }}
                        tr:nth-child(even) {{ background-color: #f9f9f9; }}
                        .container {{ margin-bottom: 30px; }}
                        .summary {{ background-color: #eef; padding: 15px; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <h1>API Metrics Report</h1>
                    <p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

                    <div class="container">
                        <h2>Visualization</h2>
                        <img src="data:image/png;base64,{plot_data}" alt="API Metrics Visualization">
                    </div>

                    <div class="container summary">
                        <h2>Summary Statistics</h2>
                        <table>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                """

                # Add summary stats
                summary = api_metrics_logger.get_summary_stats()
                for key, value in summary.items():
                    if key == "average_request_time":
                        value = f"{value*1000:.2f} ms"
                    elif key == "total_cost":
                        value = f"${value:.4f}"
                    html_content += f"""
                            <tr>
                                <td>{key.replace('_', ' ').title()}</td>
                                <td>{value}</td>
                            </tr>
                    """

                html_content += """
                        </table>
                    </div>
                """

                # Add per-API statistics
                for api in api_metrics_logger.get_all_apis():
                    stats = api_metrics_logger.get_api_stats(api)
                    html_content += f"""
                    <div class="container">
                        <h2>{api.upper()} API</h2>
                        <table>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                            <tr>
                                <td>Total Calls</td>
                                <td>{stats['call_count']}</td>
                            </tr>
                            <tr>
                                <td>Success Rate</td>
                                <td>{stats['success_rate']*100:.1f}%</td>
                            </tr>
                            <tr>
                                <td>Average Response Time</td>
                                <td>{stats['average_request_time']*1000:.2f} ms</td>
                            </tr>
                    """

                    if 'total_cost' in stats and stats['total_cost'] is not None:
                        html_content += f"""
                            <tr>
                                <td>Total Cost</td>
                                <td>${stats['total_cost']:.4f}</td>
                            </tr>
                        """

                    if 'total_tokens' in stats and stats['total_tokens'] is not None:
                        html_content += f"""
                            <tr>
                                <td>Total Tokens</td>
                                <td>{stats['total_tokens']}</td>
                            </tr>
                        """

                    html_content += """
                        </table>
                    </div>
                    """

                html_content += """
                </body>
                </html>
                """

                with open(report_path, "w") as f:
                    f.write(html_content)
            except ImportError:
                # Fall back to JSON if visualization libraries are not available
                report_path = output_dir / f"api_metrics_report_{timestamp}.json"
                with open(report_path, "w") as f:
                    import json
                    json.dump(api_metrics_logger.get_summary(), f, indent=2)
        else:
            raise ValueError(f"Unsupported report format: {format}")

        return str(report_path)

    return _generate_report


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus, config: Config):
    """Add API metrics summary to the terminal output at the end of testing."""
    if not config.getoption("log_metrics"):
        return

    if hasattr(config, "_api_metrics_logger") and config._api_metrics_logger is not None:
        metrics_logger = config._api_metrics_logger

        terminalreporter.write_sep("=", "API Metrics Summary")

        # Print overall summary
        summary = metrics_logger.get_summary_stats()
        terminalreporter.write_line(f"Total API Calls: {summary['total_calls']}")
        terminalreporter.write_line(f"Overall Success Rate: {summary['success_rate']*100:.1f}%")
        terminalreporter.write_line(f"Average Response Time: {summary['average_request_time']*1000:.2f} ms")

        if summary.get('total_cost') is not None:
            terminalreporter.write_line(f"Total Estimated Cost: ${summary['total_cost']:.4f}")

        # Print per-API summary
        terminalreporter.write_sep("-", "Per-API Statistics")
        for api in metrics_logger.get_all_apis():
            stats = metrics_logger.get_api_stats(api)
            terminalreporter.write_line(f"\n{api.upper()} API:")
            terminalreporter.write_line(f"  Calls: {stats['call_count']}")
            terminalreporter.write_line(f"  Success Rate: {stats['success_rate']*100:.1f}%")
            terminalreporter.write_line(f"  Avg Response Time: {stats['average_request_time']*1000:.2f} ms")

            if 'total_cost' in stats and stats['total_cost'] is not None:
                terminalreporter.write_line(f"  Estimated Cost: ${stats['total_cost']:.4f}")

            if 'total_tokens' in stats and stats['total_tokens'] is not None:
                terminalreporter.write_line(f"  Total Tokens: {stats['total_tokens']}")

        # Generate report if requested
        if config.getoption("generate_report"):
            try:
                # Generate report in all formats
                json_report = metrics_logger.metrics_report(format="json")
                terminalreporter.write_sep("-", "API Metrics Reports Generated")
                terminalreporter.write_line(f"JSON Report: {json_report}")

                try:
                    csv_report = metrics_logger.metrics_report(format="csv")
                    terminalreporter.write_line(f"CSV Report: {csv_report}")
                except Exception as e:
                    terminalreporter.write_line(f"CSV Report generation failed: {str(e)}")

                try:
                    html_report = metrics_logger.metrics_report(format="html")
                    terminalreporter.write_line(f"HTML Report: {html_report}")
                except Exception as e:
                    terminalreporter.write_line(f"HTML Report generation failed: {str(e)}")

            except Exception as e:
                terminalreporter.write_line(f"Report generation failed: {str(e)}")


# TEMPORARILY DISABLED: sys.path modifications to test package imports
# Add project root to Python path for integration tests
# project_root = Path(__file__).parent.parent.parent
# if str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))

# Set up test environment variables
os.environ.setdefault("TEST_MODE", "True")
os.environ.setdefault("MOCK_EXTERNAL_APIS", "True")
