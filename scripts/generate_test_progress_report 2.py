#!/usr/bin/env python3
"""
Generate Test Progress Report

This script generates a comprehensive report on the progress of test re-enablement
in the CI pipeline. It analyzes the test history and status to provide insights
into our progress and identify areas that need attention.

Usage:
    python scripts/generate_test_progress_report.py [--output=<file>]

Options:
    --output=<file>    Output file for the report (default: test_results/progress_report.md)
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Try to import visualization libraries, but don't fail if they're not available
try:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import typing modules for type annotations

# Import test status tracker constants
from scripts.test_status_tracker import (
    CATEGORIES,
    STATUS_DISABLED,
    STATUS_FAILING,
    STATUS_PASSING,
    STATUS_SKIPPED,
    TestStatusTracker,
)


class TestProgressReporter:
    """Generates reports on test re-enablement progress."""

    def __init__(self):
        self.tracker = TestStatusTracker()
        self.history = self.tracker.history
        self.output_dir = project_root / "test_results"
        os.makedirs(self.output_dir, exist_ok=True)

    def calculate_progress_metrics(self) -> Dict[str, Any]:
        """Calculate metrics for test re-enablement progress."""
        metrics: Dict[str, Any] = {}

        # Current status counts
        status_counts: Dict[str, int] = defaultdict(int)
        category_status: Dict[str, Dict[str, int]] = {}

        for category in CATEGORIES:
            category_status[category] = defaultdict(int)

        for test_id, test_info in self.tracker.tests.items():
            status = test_info["status"]
            category = test_info.get("category", "other")

            status_counts[status] += 1
            category_status[category][status] += 1

        metrics["total_tests"] = len(self.tracker.tests)
        metrics["status_counts"] = dict(status_counts)
        metrics["category_status"] = {k: dict(v) for k, v in category_status.items()}

        # Calculate progress percentage
        if metrics["total_tests"] > 0:
            metrics["progress_percentage"] = (
                (status_counts[STATUS_PASSING] + status_counts[STATUS_SKIPPED])
                / metrics["total_tests"]
                * 100
            )
        else:
            metrics["progress_percentage"] = 0

        # Calculate progress over time
        if self.history["runs"]:
            progress_over_time: List[Dict[str, Any]] = []

            for run in sorted(self.history["runs"], key=lambda x: x["timestamp"]):
                timestamp = datetime.fromisoformat(run["timestamp"])
                passing = sum(
                    1 for r in run["results"].values() if r["status"] == STATUS_PASSING
                )
                failing = sum(
                    1 for r in run["results"].values() if r["status"] == STATUS_FAILING
                )
                skipped = sum(
                    1 for r in run["results"].values() if r["status"] == STATUS_SKIPPED
                )
                total = len(run["results"])

                if total > 0:
                    progress_percentage = (passing + skipped) / total * 100
                else:
                    progress_percentage = 0

                progress_over_time.append(
                    {
                        "timestamp": timestamp,
                        "passing": passing,
                        "failing": failing,
                        "skipped": skipped,
                        "total": total,
                        "progress_percentage": progress_percentage,
                    }
                )

            metrics["progress_over_time"] = progress_over_time

        # Calculate failure trends
        if self.history["runs"] and len(self.history["runs"]) >= 2:
            failure_trends: dict[str, list[str]] = defaultdict(list)

            for run in sorted(self.history["runs"], key=lambda x: x["timestamp"]):
                for test_id, result in run["results"].items():
                    if result["status"] == STATUS_FAILING:
                        failure_trends[test_id].append(run["timestamp"])

            # Find persistent failures (failing in multiple runs)
            persistent_failures: list[tuple[str, int]] = []
            for test_id, timestamps in failure_trends.items():
                if len(timestamps) >= 2:
                    persistent_failures.append((test_id, len(timestamps)))

            # Sort by number of failures (descending)
            persistent_failures.sort(key=lambda x: x[1], reverse=True)
            metrics["persistent_failures"] = persistent_failures

        return metrics

    def generate_visualizations(self, metrics: dict):
        """Generate visualizations for the progress report."""
        if not HAS_VISUALIZATION:
            return

        # Create visualization directory
        os.makedirs(self.output_dir / "visualizations", exist_ok=True)

        # 1. Progress over time line chart
        if "progress_over_time" in metrics and metrics["progress_over_time"]:
            self._create_progress_line_chart(metrics["progress_over_time"])

        # 2. Status distribution pie chart
        if "status_counts" in metrics:
            self._create_status_pie_chart(metrics["status_counts"])

        # 3. Category progress stacked bar chart
        if "category_status" in metrics:
            self._create_category_progress_chart(metrics["category_status"])

    def _create_progress_line_chart(self, progress_data: list[dict]):
        """Create a line chart showing progress over time."""
        dates = [entry["timestamp"] for entry in progress_data]
        progress = [entry["progress_percentage"] for entry in progress_data]

        plt.figure(figsize=(12, 6))
        plt.plot(dates, progress, "b-", marker="o", linewidth=2)

        plt.xlabel("Date")
        plt.ylabel("Progress (%)")
        plt.title("Test Re-enablement Progress Over Time")
        plt.grid(True)
        plt.ylim(0, 100)

        # Add trend line
        if len(dates) >= 2:
            z = np.polyfit(range(len(dates)), progress, 1)
            p = np.poly1d(z)
            plt.plot(dates, p(range(len(dates))), "r--", linewidth=1)

        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/visualizations/progress_line_chart.png")
        plt.close()

    def _create_status_pie_chart(self, status_counts: dict[str, int]):
        """Create a pie chart of test status distribution."""
        plt.figure(figsize=(10, 6))
        labels = list(status_counts.keys())
        sizes = list(status_counts.values())
        colors = ["green", "red", "gray", "orange"]

        plt.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
        plt.axis("equal")
        plt.title("Test Status Distribution")
        plt.savefig(f"{self.output_dir}/visualizations/status_pie_chart.png")
        plt.close()

    def _create_category_progress_chart(
        self, category_status: dict[str, dict[str, int]]
    ):
        """Create a stacked bar chart showing progress by category."""
        categories = []
        passing = []
        failing = []
        disabled = []
        skipped = []

        for category, statuses in category_status.items():
            if sum(statuses.values()) > 0:
                categories.append(category)
                passing.append(statuses.get(STATUS_PASSING, 0))
                failing.append(statuses.get(STATUS_FAILING, 0))
                disabled.append(statuses.get(STATUS_DISABLED, 0))
                skipped.append(statuses.get(STATUS_SKIPPED, 0))

        plt.figure(figsize=(12, 8))
        bar_width = 0.6
        indices = np.arange(len(categories))

        plt.bar(indices, passing, bar_width, color="green", label=STATUS_PASSING)
        plt.bar(
            indices,
            failing,
            bar_width,
            bottom=passing,
            color="red",
            label=STATUS_FAILING,
        )
        plt.bar(
            indices,
            disabled,
            bar_width,
            bottom=np.array(passing) + np.array(failing),
            color="gray",
            label=STATUS_DISABLED,
        )
        plt.bar(
            indices,
            skipped,
            bar_width,
            bottom=np.array(passing) + np.array(failing) + np.array(disabled),
            color="orange",
            label=STATUS_SKIPPED,
        )

        plt.xlabel("Category")
        plt.ylabel("Number of Tests")
        plt.title("Test Progress by Category")
        plt.xticks(indices, categories, rotation=45, ha="right")
        plt.legend()
        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/visualizations/category_progress_chart.png")
        plt.close()

    def generate_markdown_report(self, metrics: dict, output_file: str = None) -> str:
        """Generate a markdown report of test re-enablement progress."""
        if not output_file:
            output_file = f"{self.output_dir}/progress_report.md"

        report_lines = [
            "# Test Re-enablement Progress Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"Total tests: {metrics['total_tests']}",
            f"Overall progress: {metrics['progress_percentage']:.1f}%",
            "",
            "### Status Distribution",
            "",
            f"- **Passing**: {metrics['status_counts'].get(STATUS_PASSING, 0)} tests ({metrics['status_counts'].get(STATUS_PASSING, 0) / metrics['total_tests'] * 100:.1f}%)",
            f"- **Failing**: {metrics['status_counts'].get(STATUS_FAILING, 0)} tests ({metrics['status_counts'].get(STATUS_FAILING, 0) / metrics['total_tests'] * 100:.1f}%)",
            f"- **Disabled**: {metrics['status_counts'].get(STATUS_DISABLED, 0)} tests ({metrics['status_counts'].get(STATUS_DISABLED, 0) / metrics['total_tests'] * 100:.1f}%)",
            f"- **Skipped**: {metrics['status_counts'].get(STATUS_SKIPPED, 0)} tests ({metrics['status_counts'].get(STATUS_SKIPPED, 0) / metrics['total_tests'] * 100:.1f}%)",
            "",
            "## Progress by Category",
            "",
        ]

        # Add category progress table
        report_lines.append(
            "| Union[Category, Total] | Union[Passing, Failing] | Union[Disabled, Skipped] | Progress |"
        )
        report_lines.append(
            "|----------|-------|---------|---------|----------|---------|----------|"
        )

        for category, statuses in metrics["category_status"].items():
            total = sum(statuses.values())
            if total > 0:
                passing = statuses.get(STATUS_PASSING, 0)
                failing = statuses.get(STATUS_FAILING, 0)
                disabled = statuses.get(STATUS_DISABLED, 0)
                skipped = statuses.get(STATUS_SKIPPED, 0)
                progress = (passing + skipped) / total * 100 if total > 0 else 0

                report_lines.append(
                    f"| {category} | {total} | {passing} | {failing} | {disabled} | {skipped} | {progress:.1f}% |"
                )

        # Add progress over time section
        if "progress_over_time" in metrics and metrics["progress_over_time"]:
            report_lines.extend(
                [
                    "",
                    "## Progress Over Time",
                    "",
                    "| Union[Date, Passing] | Union[Failing, Skipped] | Union[Total, Progress] |",
                    "|------|---------|---------|---------|-------|----------|",
                ]
            )

            for entry in metrics["progress_over_time"][-10:]:  # Show last 10 entries
                date_str = entry["timestamp"].strftime("%Y-%m-%d")
                report_lines.append(
                    f"| {date_str} | {entry['passing']} | {entry['failing']} | {entry['skipped']} | {entry['total']} | {entry['progress_percentage']:.1f}% |"
                )

        # Add persistent failures section
        if "persistent_failures" in metrics and metrics["persistent_failures"]:
            report_lines.extend(
                [
                    "",
                    "## Persistent Failures",
                    "",
                    "These tests have failed consistently across multiple runs and should be prioritized for fixing:",
                    "",
                    "| Union[Test, Failure] Count |",
                    "|------|---------------|",
                ]
            )

            for test_id, count in metrics["persistent_failures"][:10]:  # Show top 10
                test_info = self.tracker.tests.get(test_id, {})
                test_name = f"{test_info.get('file', 'Unknown')}::{test_info.get('function', 'Unknown')}"
                report_lines.append(f"| {test_name} | {count} |")

        # Add recommendations section
        report_lines.extend(["", "## Recommendations", ""])

        # Add category-specific recommendations
        low_progress_categories = []
        for category, statuses in metrics["category_status"].items():
            total = sum(statuses.values())
            if total > 0:
                passing = statuses.get(STATUS_PASSING, 0)
                skipped = statuses.get(STATUS_SKIPPED, 0)
                progress = (passing + skipped) / total * 100

                if progress < 50:
                    low_progress_categories.append((category, progress))

        if low_progress_categories:
            report_lines.append("### Focus Areas")
            report_lines.append("")
            report_lines.append(
                "These categories have low progress and should be prioritized:"
            )
            report_lines.append("")

            for category, progress in sorted(
                low_progress_categories, key=lambda x: x[1]
            ):
                report_lines.append(f"- **{category}**: {progress:.1f}% complete")

        # Add next steps
        report_lines.extend(
            [
                "",
                "### Next Steps",
                "",
                "1. **Fix persistent failures** - Address the tests that consistently fail across multiple runs",
                "2. **Enable more tests** - Use the test prioritization script to enable more tests",
                "3. **Focus on low-progress categories** - Prioritize categories with low progress",
                "4. **Update test dependencies** - Ensure test dependencies are correctly identified",
                "",
                "## Visualizations",
                "",
                "### Progress Over Time",
                "![Progress Over Time](visualizations/progress_line_chart.png)",
                "",
                "### Status Distribution",
                "![Status Distribution](visualizations/status_pie_chart.png)",
                "",
                "### Category Progress",
                "![Category Progress](visualizations/category_progress_chart.png)",
            ]
        )

        report_text = "\n".join(report_lines)

        # Write to file
        with open(output_file, "w") as f:
            f.write(report_text)

        return report_text

    def generate_report(self, output_file: str = None):
        """Generate a comprehensive progress report."""
        metrics = self.calculate_progress_metrics()
        self.generate_visualizations(metrics)
        return self.generate_markdown_report(metrics, output_file)


def main():
    parser = argparse.ArgumentParser(description="Generate Test Progress Report")
    parser.add_argument("--output", type=str, help="Output file for the report")

    args = parser.parse_args()

    reporter = TestProgressReporter()
    reporter.generate_report(output_file=args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
