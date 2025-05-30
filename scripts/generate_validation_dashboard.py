#!/usr/bin/env python3
"""
Generate a dashboard for visualizing large-scale validation results over time.
This script collects performance metrics from previous validation runs and
generates an HTML dashboard with interactive charts.
"""

import argparse
import datetime
import glob
import json
import os
import sys
from collections import defaultdict

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from jinja2 import Template
from matplotlib.ticker import MaxNLocator

# Configure Matplotlib and Seaborn
plt.style.use("ggplot")
sns.set_theme(style="whitegrid")

# Define dashboard template
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LeadFactory Large-Scale Validation Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding-top: 20px;
            background-color: #f8f9fa;
        }
        .card {
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .card-header {
            font-weight: bold;
            background-color: #e9ecef;
        }
        .status-badge {
            font-size: 1.2rem;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
        }
        .metric-label {
            font-size: 0.9rem;
            color: #6c757d;
        }
        .trend-indicator {
            font-size: 1.5rem;
            margin-left: 10px;
        }
        .trend-up {
            color: #28a745;
        }
        .trend-down {
            color: #dc3545;
        }
        .trend-neutral {
            color: #6c757d;
        }
        .chart-container {
            position: relative;
            height: 300px;
            width: 100%;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row mb-4">
            <div class="col-12">
                <h1 class="display-4 text-center">LeadFactory Large-Scale Validation Dashboard</h1>
                <p class="text-center text-muted">
                    Last updated: {{ last_updated }}
                </p>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>Current Status</span>
                        <span class="status-badge badge {{ status_color }}">{{ status_text }}</span>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-3 text-center">
                                <div class="metric-value">{{ latest_metrics.throughput|round(1) }}
                                    <span class="trend-indicator {{ throughput_trend_class }}">{{ throughput_trend }}</span>
                                </div>
                                <div class="metric-label">Leads/Minute</div>
                            </div>
                            <div class="col-md-3 text-center">
                                <div class="metric-value">{{ (latest_metrics.error_rate * 100)|round(2) }}%
                                    <span class="trend-indicator {{ error_trend_class }}">{{ error_trend }}</span>
                                </div>
                                <div class="metric-label">Error Rate</div>
                            </div>
                            <div class="col-md-3 text-center">
                                <div class="metric-value">{{ latest_metrics.runtime|round(1) }}
                                    <span class="trend-indicator {{ runtime_trend_class }}">{{ runtime_trend }}</span>
                                </div>
                                <div class="metric-label">Runtime (min)</div>
                            </div>
                            <div class="col-md-3 text-center">
                                <div class="metric-value">{{ latest_metrics.lead_count|int }}
                                    <span class="trend-indicator"></span>
                                </div>
                                <div class="metric-label">Leads Processed</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-header">Throughput Over Time</div>
                    <div class="card-body">
                        <div class="chart-container">
                            <img src="charts/throughput_trend.png" class="img-fluid" alt="Throughput Trend">
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-header">Error Rate Over Time</div>
                    <div class="card-body">
                        <div class="chart-container">
                            <img src="charts/error_rate_trend.png" class="img-fluid" alt="Error Rate Trend">
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-header">Runtime Trend</div>
                    <div class="card-body">
                        <div class="chart-container">
                            <img src="charts/runtime_trend.png" class="img-fluid" alt="Runtime Trend">
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-header">Pipeline Component Performance</div>
                    <div class="card-body">
                        <div class="chart-container">
                            <img src="charts/component_performance.png" class="img-fluid" alt="Component Performance">
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">Recent Validation Runs</div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped table-hover">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Lead Count</th>
                                        <th>Throughput</th>
                                        <th>Error Rate</th>
                                        <th>Runtime (min)</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for run in recent_runs %}
                                    <tr>
                                        <td>{{ run.date }}</td>
                                        <td>{{ run.lead_count }}</td>
                                        <td>{{ run.throughput|round(1) }}</td>
                                        <td>{{ (run.error_rate * 100)|round(2) }}%</td>
                                        <td>{{ run.runtime|round(1) }}</td>
                                        <td>
                                            <span class="badge {{ run.status_color }}">{{ run.status }}</span>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer class="bg-light py-3 mt-5">
        <div class="container text-center">
            <p class="text-muted mb-0">
                LeadFactory Validation Dashboard -
                <a href="https://github.com/mirqtio/Anthrasite_LeadFactory">GitHub Repository</a>
            </p>
        </div>
    </footer>
</body>
</html>
"""


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate large-scale validation dashboard"
    )
    parser.add_argument(
        "--metrics-dir",
        default="performance_reports",
        help="Directory containing performance metrics",
    )
    parser.add_argument(
        "--output-dir",
        default="performance_reports/dashboard",
        help="Directory to output dashboard files",
    )
    parser.add_argument(
        "--history-file",
        default="performance_reports/validation_history.json",
        help="JSON file containing historical validation metrics",
    )
    parser.add_argument(
        "--max-history",
        type=int,
        default=30,
        help="Maximum number of historical runs to display",
    )
    return parser.parse_args()


def find_metrics_files(metrics_dir):
    """Find all metrics JSON files in the specified directory."""
    return glob.glob(os.path.join(metrics_dir, "*.json"))


def load_historical_data(history_file):
    """Load historical validation data from JSON file."""
    if os.path.exists(history_file):
        with open(history_file) as f:
            return json.load(f)
    return []


def update_historical_data(history_file, metrics_files, history_data, max_history):
    """Update historical data with new metrics."""
    existing_dates = {run["run_id"] for run in history_data}

    for metrics_file in metrics_files:
        try:
            with open(metrics_file) as f:
                metrics = json.load(f)

            if "run_id" in metrics and metrics["run_id"] not in existing_dates:
                # Add timestamp if not present
                if "timestamp" not in metrics:
                    metrics["timestamp"] = datetime.datetime.now().isoformat()

                # Add formatted date
                if "timestamp" in metrics:
                    try:
                        date_obj = datetime.datetime.fromisoformat(metrics["timestamp"])
                        metrics["date"] = date_obj.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        metrics["date"] = "Unknown"

                history_data.append(metrics)
        except (OSError, json.JSONDecodeError):
            pass

    # Sort by timestamp (newest first) and limit to max_history
    history_data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    if max_history > 0:
        history_data = history_data[:max_history]

    # Save updated history
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history_data, f, indent=2)

    return history_data


def calculate_trends(history_data):
    """Calculate trends from historical data."""
    if len(history_data) < 2:
        return {
            "throughput_trend": "neutral",
            "error_trend": "neutral",
            "runtime_trend": "neutral",
        }

    # Get latest and previous metrics
    latest = history_data[0]
    previous = history_data[1]

    # Calculate trend directions
    throughput_trend = "neutral"
    if latest.get("throughput", 0) > previous.get("throughput", 0) * 1.05:
        throughput_trend = "up"
    elif latest.get("throughput", 0) < previous.get("throughput", 0) * 0.95:
        throughput_trend = "down"

    error_trend = "neutral"
    if latest.get("error_rate", 0) < previous.get("error_rate", 0) * 0.95:
        error_trend = "up"  # Improved (lower error rate)
    elif latest.get("error_rate", 0) > previous.get("error_rate", 0) * 1.05:
        error_trend = "down"  # Worse (higher error rate)

    runtime_trend = "neutral"
    if latest.get("runtime", 0) < previous.get("runtime", 0) * 0.95:
        runtime_trend = "up"  # Improved (faster runtime)
    elif latest.get("runtime", 0) > previous.get("runtime", 0) * 1.05:
        runtime_trend = "down"  # Worse (slower runtime)

    return {
        "throughput_trend": throughput_trend,
        "error_trend": error_trend,
        "runtime_trend": runtime_trend,
    }


def generate_trend_charts(history_data, output_dir):
    """Generate trend charts for the dashboard."""
    os.makedirs(os.path.join(output_dir, "charts"), exist_ok=True)

    # Convert to pandas DataFrame for easier plotting
    df = pd.DataFrame(history_data)
    if len(df) == 0:
        return

    # Convert timestamp to datetime
    df["datetime"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("datetime")

    # Throughput trend chart
    plt.figure(figsize=(10, 6))
    plt.plot(df["datetime"], df["throughput"], marker="o", linewidth=2)
    plt.axhline(y=100, color="r", linestyle="--", alpha=0.7, label="Minimum Threshold")
    plt.title("Throughput Over Time", fontsize=14)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Leads/Minute", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df) // 10)))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "charts", "throughput_trend.png"))
    plt.close()

    # Error rate trend chart
    plt.figure(figsize=(10, 6))
    plt.plot(
        df["datetime"], df["error_rate"] * 100, marker="o", linewidth=2, color="#d62728"
    )
    plt.axhline(y=1, color="r", linestyle="--", alpha=0.7, label="Maximum Threshold")
    plt.title("Error Rate Over Time", fontsize=14)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Error Rate (%)", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df) // 10)))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "charts", "error_rate_trend.png"))
    plt.close()

    # Runtime trend chart
    plt.figure(figsize=(10, 6))
    plt.plot(df["datetime"], df["runtime"], marker="o", linewidth=2, color="#2ca02c")
    plt.axhline(y=180, color="r", linestyle="--", alpha=0.7, label="Maximum Threshold")
    plt.title("Runtime Trend", fontsize=14)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Runtime (minutes)", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df) // 10)))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "charts", "runtime_trend.png"))
    plt.close()

    # Component performance chart (if component timing data is available)
    if (
        "component_timings" in df.columns
        and len(df) > 0
        and df.iloc[-1]["component_timings"]
    ):
        latest_components = df.iloc[-1]["component_timings"]

        if isinstance(latest_components, str):
            try:
                latest_components = json.loads(latest_components)
            except json.JSONDecodeError:
                latest_components = {}

        if latest_components and isinstance(latest_components, dict):
            components = list(latest_components.keys())
            times = list(latest_components.values())

            plt.figure(figsize=(10, 6))
            bars = plt.barh(
                components, times, color=sns.color_palette("viridis", len(components))
            )
            plt.title("Pipeline Component Performance", fontsize=14)
            plt.xlabel("Processing Time (seconds)", fontsize=12)
            plt.ylabel("Component", fontsize=12)
            plt.grid(True, alpha=0.3, axis="x")

            # Add time values at the end of each bar
            for bar in bars:
                width = bar.get_width()
                plt.text(
                    width + 0.3,
                    bar.get_y() + bar.get_height() / 2,
                    f"{width:.1f}s",
                    ha="left",
                    va="center",
                )

            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, "charts", "component_performance.png"))
            plt.close()


def generate_dashboard(history_data, output_dir):
    """Generate HTML dashboard."""
    if not history_data:
        return

    # Prepare data for template
    latest_metrics = history_data[0]

    # Calculate trends
    trends = calculate_trends(history_data)

    # Prepare status indicators
    status_text = "Passing"
    status_color = "bg-success text-white"

    if (
        latest_metrics.get("throughput", 0) < 100
        or latest_metrics.get("error_rate", 0) > 0.01
        or latest_metrics.get("runtime", 0) > 180
    ):
        status_text = "Failing"
        status_color = "bg-danger text-white"

    # Prepare trend indicators
    trend_symbols = {"up": "↑", "down": "↓", "neutral": "→"}

    trend_classes = {"up": "trend-up", "down": "trend-down", "neutral": "trend-neutral"}

    # Special case for error rate where down is good
    error_trend_class = "trend-neutral"
    if trends["error_trend"] == "up":
        error_trend_class = "trend-up"
    elif trends["error_trend"] == "down":
        error_trend_class = "trend-down"

    # Format data for recent runs table
    recent_runs = []
    for run in history_data[:10]:  # Last 10 runs
        run_status = "Passing"
        run_status_color = "bg-success text-white"

        if (
            run.get("throughput", 0) < 100
            or run.get("error_rate", 0) > 0.01
            or run.get("runtime", 0) > 180
        ):
            run_status = "Failing"
            run_status_color = "bg-danger text-white"

        recent_runs.append(
            {
                "date": run.get("date", "Unknown"),
                "lead_count": run.get("lead_count", 0),
                "throughput": run.get("throughput", 0),
                "error_rate": run.get("error_rate", 0),
                "runtime": run.get("runtime", 0),
                "status": run_status,
                "status_color": run_status_color,
            }
        )

    # Render template
    template = Template(DASHBOARD_TEMPLATE)
    html = template.render(
        last_updated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        latest_metrics=latest_metrics,
        status_text=status_text,
        status_color=status_color,
        throughput_trend=trend_symbols[trends["throughput_trend"]],
        error_trend=trend_symbols[trends["error_trend"]],
        runtime_trend=trend_symbols[trends["runtime_trend"]],
        throughput_trend_class=trend_classes[trends["throughput_trend"]],
        error_trend_class=error_trend_class,
        runtime_trend_class=trend_classes[trends["runtime_trend"]],
        recent_runs=recent_runs,
    )

    # Write HTML file
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(html)


def main():
    """Main function."""
    args = parse_args()

    # Ensure output directories exist
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "charts"), exist_ok=True)

    # Find metrics files
    metrics_files = find_metrics_files(args.metrics_dir)
    if not metrics_files:
        return 1

    # Load and update historical data
    history_data = load_historical_data(args.history_file)
    history_data = update_historical_data(
        args.history_file, metrics_files, history_data, args.max_history
    )

    # Generate trend charts
    generate_trend_charts(history_data, args.output_dir)

    # Generate dashboard
    generate_dashboard(history_data, args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
