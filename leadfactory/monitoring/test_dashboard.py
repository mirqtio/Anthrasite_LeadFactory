"""
Web-based Test Monitoring Dashboard.

Provides a web interface for visualizing test metrics and CI pipeline health.
Part of Task 14: CI Pipeline Test Monitoring and Governance Framework.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from .test_monitoring import get_test_health_report, metrics_collector

app = Flask(__name__)


@app.route("/")
def dashboard():
    """Main dashboard page."""
    return render_template("test_dashboard.html")


@app.route("/api/summary")
def api_summary():
    """Get dashboard summary statistics."""
    try:
        summary = metrics_collector.get_dashboard_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tests")
def api_tests():
    """Get test metrics with filtering and pagination."""
    try:
        limit = int(request.args.get("limit", 50))
        suite_filter = request.args.get("suite", "")
        grade_filter = request.args.get("grade", "")

        all_tests = metrics_collector.get_all_test_metrics(
            limit=limit * 2
        )  # Get more for filtering

        # Apply filters
        filtered_tests = all_tests
        if suite_filter:
            filtered_tests = [
                t
                for t in filtered_tests
                if suite_filter.lower() in t.test_suite.lower()
            ]
        if grade_filter:
            filtered_tests = [
                t for t in filtered_tests if t.reliability_grade == grade_filter.upper()
            ]

        # Limit results
        filtered_tests = filtered_tests[:limit]

        return jsonify(
            [
                {
                    "test_id": test.test_id,
                    "test_name": test.test_name,
                    "test_suite": test.test_suite,
                    "pass_rate": round(test.pass_rate * 100, 1),
                    "avg_duration": round(test.avg_duration, 2),
                    "flakiness_score": round(test.flakiness_score * 100, 1),
                    "execution_count": test.execution_count,
                    "last_execution": test.last_execution.isoformat(),
                    "trend": test.trend,
                    "reliability_grade": test.reliability_grade,
                }
                for test in filtered_tests
            ]
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/problematic-tests")
def api_problematic_tests():
    """Get tests that need attention."""
    try:
        pass_rate_threshold = float(request.args.get("pass_rate", 0.8))
        flakiness_threshold = float(request.args.get("flakiness", 0.3))

        problematic_tests = metrics_collector.get_problematic_tests(
            threshold_pass_rate=pass_rate_threshold,
            threshold_flakiness=flakiness_threshold,
        )

        return jsonify(
            [
                {
                    "test_id": test.test_id,
                    "test_name": test.test_name,
                    "test_suite": test.test_suite,
                    "pass_rate": round(test.pass_rate * 100, 1),
                    "flakiness_score": round(test.flakiness_score * 100, 1),
                    "reliability_grade": test.reliability_grade,
                    "trend": test.trend,
                    "execution_count": test.execution_count,
                    "issue_type": (
                        "low_pass_rate"
                        if test.pass_rate < pass_rate_threshold
                        else "flaky"
                    ),
                }
                for test in problematic_tests
            ]
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/suite/<suite_name>")
def api_suite_details(suite_name):
    """Get detailed metrics for a specific test suite."""
    try:
        suite_metrics = metrics_collector.get_suite_metrics(suite_name)

        return jsonify(
            {
                "suite_name": suite_metrics.suite_name,
                "total_tests": suite_metrics.total_tests,
                "pass_rate": round(suite_metrics.pass_rate * 100, 1),
                "avg_duration": round(suite_metrics.avg_duration, 2),
                "flaky_tests": suite_metrics.flaky_tests,
                "critical_failures": suite_metrics.critical_failures,
                "last_run": suite_metrics.last_run.isoformat(),
                "health_status": suite_metrics.health_status,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/test/<path:test_id>")
def api_test_details(test_id):
    """Get detailed metrics for a specific test."""
    try:
        test_metrics = metrics_collector.get_test_metrics(test_id)

        if not test_metrics:
            return jsonify({"error": "Test not found"}), 404

        return jsonify(
            {
                "test_id": test_metrics.test_id,
                "test_name": test_metrics.test_name,
                "test_suite": test_metrics.test_suite,
                "pass_rate": round(test_metrics.pass_rate * 100, 1),
                "avg_duration": round(test_metrics.avg_duration, 2),
                "flakiness_score": round(test_metrics.flakiness_score * 100, 1),
                "execution_count": test_metrics.execution_count,
                "last_execution": test_metrics.last_execution.isoformat(),
                "trend": test_metrics.trend,
                "reliability_grade": test_metrics.reliability_grade,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health-report")
def api_health_report():
    """Get comprehensive test health report."""
    try:
        report = get_test_health_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh")
def api_refresh():
    """Refresh all test metrics."""
    try:
        metrics_collector.refresh_all_metrics()
        return jsonify({"status": "success", "message": "Metrics refreshed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Ensure templates directory exists
if not os.path.exists("templates"):
    os.makedirs("templates")

# Create the HTML template
dashboard_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Monitoring Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .metric-label {
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .grade-indicator {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
            margin: 2px;
        }
        .grade-a { background-color: #4CAF50; }
        .grade-b { background-color: #8BC34A; }
        .grade-c { background-color: #FFC107; }
        .grade-d { background-color: #FF9800; }
        .grade-f { background-color: #F44336; }
        .test-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .test-table th, .test-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .test-table th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        .trend-improving { color: #4CAF50; }
        .trend-stable { color: #2196F3; }
        .trend-degrading { color: #F44336; }
        .status-healthy { color: #4CAF50; }
        .status-warning { color: #FF9800; }
        .status-critical { color: #F44336; }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .refresh-btn:hover {
            background: #5a6fd8;
        }
        .loading {
            text-align: center;
            color: #666;
            padding: 20px;
        }
        .error {
            background-color: #ffebee;
            color: #c62828;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>CI Pipeline Test Monitoring Dashboard</h1>
        <p>Real-time visibility into test reliability and pipeline health</p>
    </div>

    <button class="refresh-btn" onclick="refreshData()">Refresh Metrics</button>

    <div class="dashboard-grid">
        <div class="card">
            <div class="metric-value" id="total-tests">-</div>
            <div class="metric-label">Total Tests</div>
        </div>
        <div class="card">
            <div class="metric-value" id="overall-pass-rate">-</div>
            <div class="metric-label">Overall Pass Rate</div>
        </div>
        <div class="card">
            <div class="metric-value" id="flaky-tests">-</div>
            <div class="metric-label">Flaky Tests</div>
        </div>
        <div class="card">
            <div class="metric-value" id="degrading-tests">-</div>
            <div class="metric-label">Degrading Tests</div>
        </div>
    </div>

    <div class="card">
        <h3>Test Reliability Distribution</h3>
        <div id="grade-distribution">
            <div class="loading">Loading...</div>
        </div>
    </div>

    <div class="card">
        <h3>Problematic Tests Requiring Attention</h3>
        <div id="problematic-tests">
            <div class="loading">Loading...</div>
        </div>
    </div>

    <div class="card">
        <h3>Test Suite Health</h3>
        <div id="suite-health">
            <div class="loading">Loading...</div>
        </div>
    </div>

    <script>
        async function fetchData(url) {
            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error('Network response was not ok');
                return await response.json();
            } catch (error) {
                console.error('Fetch error:', error);
                return null;
            }
        }

        async function loadDashboard() {
            // Load summary data
            const summary = await fetchData('/api/summary');
            if (summary) {
                updateSummary(summary);
            }

            // Load problematic tests
            const problematicTests = await fetchData('/api/problematic-tests');
            if (problematicTests) {
                updateProblematicTests(problematicTests);
            }
        }

        function updateSummary(summary) {
            document.getElementById('total-tests').textContent = summary.total_tests || 0;
            document.getElementById('overall-pass-rate').textContent =
                ((summary.overall_pass_rate || 0) * 100).toFixed(1) + '%';
            document.getElementById('flaky-tests').textContent = summary.flaky_tests || 0;
            document.getElementById('degrading-tests').textContent = summary.degrading_tests || 0;

            // Update grade distribution
            const gradeDistribution = summary.grade_distribution || {};
            const gradeHtml = Object.entries(gradeDistribution)
                .map(([grade, count]) =>
                    `<span class="grade-indicator grade-${grade.toLowerCase()}">${grade}: ${count}</span>`
                ).join('');
            document.getElementById('grade-distribution').innerHTML = gradeHtml;

            // Update suite statistics
            const suiteStats = summary.suite_statistics || [];
            const suiteHtml = suiteStats.length > 0 ? `
                <table class="test-table">
                    <thead>
                        <tr>
                            <th>Suite Name</th>
                            <th>Test Count</th>
                            <th>Pass Rate</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${suiteStats.map(suite => `
                            <tr>
                                <td>${suite.suite_name}</td>
                                <td>${suite.test_count}</td>
                                <td>${(suite.pass_rate * 100).toFixed(1)}%</td>
                                <td class="status-${getHealthStatus(suite.pass_rate)}">
                                    ${getHealthStatus(suite.pass_rate)}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            ` : '<div class="loading">No suite data available</div>';
            document.getElementById('suite-health').innerHTML = suiteHtml;
        }

        function updateProblematicTests(tests) {
            if (tests.length === 0) {
                document.getElementById('problematic-tests').innerHTML =
                    '<div style="color: #4CAF50; text-align: center; padding: 20px;">🎉 All tests are healthy!</div>';
                return;
            }

            const testsHtml = `
                <table class="test-table">
                    <thead>
                        <tr>
                            <th>Test Name</th>
                            <th>Suite</th>
                            <th>Pass Rate</th>
                            <th>Flakiness</th>
                            <th>Grade</th>
                            <th>Issue</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tests.slice(0, 20).map(test => `
                            <tr>
                                <td>${test.test_name}</td>
                                <td>${test.test_suite}</td>
                                <td>${test.pass_rate}%</td>
                                <td>${test.flakiness_score}%</td>
                                <td><span class="grade-indicator grade-${test.reliability_grade.toLowerCase()}">${test.reliability_grade}</span></td>
                                <td>${test.issue_type === 'low_pass_rate' ? 'Low Pass Rate' : 'Flaky Behavior'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            document.getElementById('problematic-tests').innerHTML = testsHtml;
        }

        function getHealthStatus(passRate) {
            if (passRate >= 0.9) return 'healthy';
            if (passRate >= 0.7) return 'warning';
            return 'critical';
        }

        async function refreshData() {
            document.querySelectorAll('.loading').forEach(el => el.style.display = 'block');

            // Trigger metrics refresh
            await fetchData('/api/refresh');

            // Reload dashboard
            await loadDashboard();
        }

        // Load dashboard on page load
        window.addEventListener('load', loadDashboard);

        // Auto-refresh every 5 minutes
        setInterval(loadDashboard, 5 * 60 * 1000);
    </script>
</body>
</html>
"""

# Save the template
template_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(template_dir, exist_ok=True)

with open(os.path.join(template_dir, "test_dashboard.html"), "w") as f:
    f.write(dashboard_template)


def run_dashboard(host="localhost", port=5000, debug=False):
    """Run the dashboard web server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard(debug=True)
