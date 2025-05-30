#!/usr/bin/env python3
"""
E2E Pipeline Report Generator

This module generates detailed reports of the E2E pipeline execution results,
including execution statistics, test coverage, and failure analysis.
"""

import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

# Configure logging
log_dir = Path(project_root) / "logs" / "e2e"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = (
    log_dir
    / f"report_generator_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates detailed reports of E2E pipeline execution results.
    """

    def __init__(
        self, execution_id: Optional[str] = None, history_file: Optional[str] = None
    ):
        """
        Initialize the ReportGenerator.

        Args:
            execution_id: ID of the specific execution to report on (if None, use latest)
            history_file: Path to the execution history JSON file
        """
        self.execution_id = execution_id
        self.history_file = history_file or str(
            project_root / "scripts" / "e2e" / "execution_history.json"
        )
        self.execution_data = None
        self.history_data = []
        self.report_data = {}

        # Load execution history
        self._load_execution_history()

        # If no execution_id specified, use the latest execution
        if not self.execution_id and self.history_data:
            self.execution_id = self.history_data[-1]["execution_id"]

        # Load the execution data for the specified ID
        self._load_execution_data()

    def _load_execution_history(self) -> None:
        """Load execution history from the history file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file) as f:
                    self.history_data = json.load(f)
                logger.info(
                    f"Loaded execution history with {len(self.history_data)} records"
                )
            else:
                logger.warning(
                    f"Execution history file not found at {self.history_file}"
                )
                self.history_data = []
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load execution history: {e}")
            self.history_data = []

    def _load_execution_data(self) -> None:
        """Load the execution data for the specified ID."""
        if not self.execution_id:
            logger.warning("No execution ID specified and no history available")
            return

        for execution in self.history_data:
            if execution["execution_id"] == self.execution_id:
                self.execution_data = execution
                logger.info(f"Loaded execution data for ID: {self.execution_id}")
                return

        logger.warning(f"No execution data found for ID: {self.execution_id}")

    def generate_summary_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate a summary report of the E2E pipeline execution.

        Args:
            output_file: Path to save the report (if None, return as string)

        Returns:
            The report content as a string if output_file is None
        """
        if not self.execution_data:
            message = "No execution data available to generate report"
            logger.error(message)
            return message

        # Build the report content
        report_content = self._build_summary_report()

        # Save to file if specified
        if output_file:
            try:
                with open(output_file, "w") as f:
                    f.write(report_content)
                logger.info(f"Summary report saved to {output_file}")
            except OSError as e:
                logger.error(f"Failed to save summary report: {e}")

        return report_content

    def generate_detailed_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate a detailed report of the E2E pipeline execution.

        Args:
            output_file: Path to save the report (if None, return as string)

        Returns:
            The report content as a string if output_file is None
        """
        if not self.execution_data:
            message = "No execution data available to generate report"
            logger.error(message)
            return message

        # Build the report content
        report_content = self._build_detailed_report()

        # Save to file if specified
        if output_file:
            try:
                with open(output_file, "w") as f:
                    f.write(report_content)
                logger.info(f"Detailed report saved to {output_file}")
            except OSError as e:
                logger.error(f"Failed to save detailed report: {e}")

        return report_content

    def generate_trend_report(
        self, num_executions: int = 10, output_file: Optional[str] = None
    ) -> str:
        """
        Generate a trend report comparing multiple executions.

        Args:
            num_executions: Number of recent executions to include
            output_file: Path to save the report (if None, return as string)

        Returns:
            The report content as a string if output_file is None
        """
        if not self.history_data:
            message = "No execution history available to generate trend report"
            logger.error(message)
            return message

        # Build the report content
        report_content = self._build_trend_report(num_executions)

        # Save to file if specified
        if output_file:
            try:
                with open(output_file, "w") as f:
                    f.write(report_content)
                logger.info(f"Trend report saved to {output_file}")
            except OSError as e:
                logger.error(f"Failed to save trend report: {e}")

        return report_content

    def _build_summary_report(self) -> str:
        """
        Build the summary report content.

        Returns:
            The report content as a string
        """
        execution = self.execution_data

        # Initialize report content
        content = []
        content.append("# E2E Pipeline Execution Summary\n")

        # Add execution metadata
        content.append("## Execution Details\n")
        content.append(f"- **Execution ID:** {execution['execution_id']}")

        # Format timestamps
        start_time = (
            datetime.datetime.fromisoformat(execution["start_time"])
            if execution.get("start_time")
            else None
        )
        end_time = (
            datetime.datetime.fromisoformat(execution["end_time"])
            if execution.get("end_time")
            else None
        )

        if start_time:
            content.append(
                f"- **Start Time:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        if end_time:
            content.append(f"- **End Time:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if start_time and end_time:
            duration = (end_time - start_time).total_seconds()
            content.append(f"- **Duration:** {duration:.2f} seconds")

        content.append(f"- **Status:** {execution['status']}")
        content.append("")

        # Add stage results
        content.append("## Stage Results\n")

        stages = execution.get("stages", {})
        for stage_name, stage_data in stages.items():
            status_icon = "✅" if stage_data.get("status") == "success" else "❌"
            content.append(f"### {status_icon} {stage_data.get('name', stage_name)}\n")

            content.append(f"- **Status:** {stage_data.get('status', 'unknown')}")

            if stage_data.get("start_time") and stage_data.get("end_time"):
                start = datetime.datetime.fromisoformat(stage_data["start_time"])
                end = datetime.datetime.fromisoformat(stage_data["end_time"])
                stage_duration = (end - start).total_seconds()
                content.append(f"- **Duration:** {stage_duration:.2f} seconds")

            if stage_data.get("retry_count", 0) > 0:
                content.append(f"- **Retries:** {stage_data['retry_count']}")

            if stage_data.get("error"):
                content.append(f"- **Error:** {stage_data['error']}")

            content.append("")

        # Add failures
        failures = execution.get("failures", [])
        if failures:
            content.append("## Failures\n")

            for failure in failures:
                content.append(f"### Failure in {failure.get('stage', 'unknown')}\n")
                content.append(f"- **Category:** {failure.get('category', 'unknown')}")
                content.append(f"- **Message:** {failure.get('message', 'No message')}")
                content.append(
                    f"- **Resolution:** {failure.get('resolution', 'No resolution')}"
                )
                content.append("")

        # Add resolution attempts
        resolution_attempts = execution.get("resolution_attempts", [])
        if resolution_attempts:
            content.append("## Resolution Attempts\n")

            for attempt in resolution_attempts:
                success_icon = "✅" if attempt.get("success", False) else "❌"
                content.append(
                    f"### {success_icon} Resolution for {attempt.get('stage', 'unknown')}\n"
                )
                content.append(f"- **Issue:** {attempt.get('issue', 'unknown')}")
                content.append(
                    f"- **Resolution:** {attempt.get('resolution', 'No resolution')}"
                )
                content.append(f"- **Result:** {attempt.get('result', 'unknown')}")
                content.append("")

        # Join all content lines
        return "\n".join(content)

    def _build_detailed_report(self) -> str:
        """
        Build the detailed report content.

        Returns:
            The report content as a string
        """
        # Start with the summary report
        content = self._build_summary_report().split("\n")

        # Add execution statistics
        self._analyze_execution_statistics()

        # Add test coverage analysis
        content.append("\n## Test Coverage Analysis\n")

        # Pipeline components coverage
        content.append("### Pipeline Components Coverage\n")

        component_coverage = self.report_data.get("component_coverage", {})
        for component, covered in component_coverage.items():
            status = "✅ Covered" if covered else "❌ Not Covered"
            content.append(f"- **{component}:** {status}")

        content.append("")

        # Add performance analysis
        content.append("### Performance Analysis\n")

        performance = self.report_data.get("performance", {})
        for metric, value in performance.items():
            content.append(f"- **{metric}:** {value}")

        content.append("")

        # Add API costs analysis
        content.append("### API Costs\n")

        # These would be extracted from the execution logs in a real implementation
        content.append("- **OpenAI API:** $X.XX")
        content.append("- **ScreenshotOne API:** $X.XX")
        content.append("- **SendGrid API:** $X.XX")
        content.append("- **Total Cost:** $X.XX")

        content.append("")

        # Add recommendations for improvement
        content.append("## Recommendations\n")

        recommendations = self.report_data.get("recommendations", [])
        for recommendation in recommendations:
            content.append(f"- {recommendation}")

        content.append("")

        # Join all content lines
        return "\n".join(content)

    def _build_trend_report(self, num_executions: int) -> str:
        """
        Build the trend report content.

        Args:
            num_executions: Number of recent executions to include

        Returns:
            The report content as a string
        """
        content = []
        content.append("# E2E Pipeline Execution Trend Report\n")

        # Use the most recent N executions
        recent_executions = (
            self.history_data[-num_executions:]
            if len(self.history_data) >= num_executions
            else self.history_data
        )

        content.append(
            f"## Trend Analysis (Last {len(recent_executions)} Executions)\n"
        )

        # Success rate
        success_count = sum(
            1 for execution in recent_executions if execution.get("status") == "success"
        )
        success_rate = (
            (success_count / len(recent_executions)) * 100 if recent_executions else 0
        )
        content.append(
            f"- **Success Rate:** {success_rate:.1f}% ({success_count}/{len(recent_executions)})"
        )

        # Average duration
        durations = []
        for execution in recent_executions:
            if execution.get("start_time") and execution.get("end_time"):
                start = datetime.datetime.fromisoformat(execution["start_time"])
                end = datetime.datetime.fromisoformat(execution["end_time"])
                durations.append((end - start).total_seconds())

        avg_duration = sum(durations) / len(durations) if durations else 0
        content.append(f"- **Average Duration:** {avg_duration:.2f} seconds")

        # Most common failures
        all_failures = []
        for execution in recent_executions:
            all_failures.extend(execution.get("failures", []))

        failure_categories = {}
        for failure in all_failures:
            category = failure.get("category", "unknown")
            failure_categories[category] = failure_categories.get(category, 0) + 1

        content.append("\n### Most Common Failure Categories\n")

        for category, count in sorted(
            failure_categories.items(), key=lambda x: x[1], reverse=True
        ):
            content.append(f"- **{category}:** {count} occurrences")

        content.append("")

        # Stage reliability
        content.append("### Stage Reliability\n")

        stage_stats = {}
        for execution in recent_executions:
            stages = execution.get("stages", {})
            for stage_name, stage_data in stages.items():
                if stage_name not in stage_stats:
                    stage_stats[stage_name] = {
                        "total": 0,
                        "success": 0,
                        "failure": 0,
                        "skipped": 0,
                    }

                stage_stats[stage_name]["total"] += 1

                status = stage_data.get("status", "unknown")
                if status == "success":
                    stage_stats[stage_name]["success"] += 1
                elif status == "failure":
                    stage_stats[stage_name]["failure"] += 1
                elif status == "skipped":
                    stage_stats[stage_name]["skipped"] += 1

        for stage_name, stats in stage_stats.items():
            success_rate = (
                (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            )
            content.append(
                f"- **{stage_name}:** {success_rate:.1f}% success rate ({stats['success']}/{stats['total']})"
            )

        content.append("")

        # Trend recommendations
        content.append("## Trend Recommendations\n")

        # These would be generated based on actual trend analysis in a real implementation
        content.append(
            "- Investigate recurring failures in the Database Connectivity stage"
        )
        content.append("- Consider adding more test coverage for Email Delivery")
        content.append(
            "- Monitor increasing execution times in the Mockup Generation stage"
        )

        content.append("")

        # Join all content lines
        return "\n".join(content)

    def _analyze_execution_statistics(self) -> None:
        """Analyze execution statistics and populate report_data."""
        execution = self.execution_data

        # Initialize report data
        self.report_data = {
            "component_coverage": {},
            "performance": {},
            "recommendations": [],
        }

        # Component coverage analysis
        pipeline_components = [
            "Configuration Validation",
            "API Connectivity",
            "Database Verification",
            "Web Scraping",
            "Screenshot Generation",
            "Mockup Generation",
            "Email Personalization",
            "Email Rendering",
            "Email Delivery",
        ]

        stages = execution.get("stages", {})
        for component in pipeline_components:
            # Check if any stage covers this component
            covered = any(
                component.lower() in stage_data.get("name", "").lower()
                and stage_data.get("status") == "success"
                for stage_data in stages.values()
            )
            self.report_data["component_coverage"][component] = covered

        # Performance analysis
        # Calculate total duration and stage durations
        if execution.get("start_time") and execution.get("end_time"):
            start = datetime.datetime.fromisoformat(execution["start_time"])
            end = datetime.datetime.fromisoformat(execution["end_time"])
            total_duration = (end - start).total_seconds()
            self.report_data["performance"][
                "Total Duration"
            ] = f"{total_duration:.2f} seconds"

            # Calculate time spent in each stage
            stage_durations = {}
            for stage_name, stage_data in stages.items():
                if stage_data.get("start_time") and stage_data.get("end_time"):
                    s_start = datetime.datetime.fromisoformat(stage_data["start_time"])
                    s_end = datetime.datetime.fromisoformat(stage_data["end_time"])
                    duration = (s_end - s_start).total_seconds()
                    stage_durations[stage_name] = duration

                    # Add to performance metrics
                    self.report_data["performance"][
                        f"{stage_data.get('name', stage_name)} Duration"
                    ] = f"{duration:.2f} seconds"

        # Generate recommendations based on execution data
        self._generate_recommendations()

    def _generate_recommendations(self) -> None:
        """Generate recommendations based on execution analysis."""
        execution = self.execution_data
        recommendations = []

        # Check for preflight failures
        preflight_check = execution.get("preflight_check", {})
        if preflight_check.get("status") == "failure":
            recommendations.append(
                "Fix environment configuration issues identified in preflight check"
            )

        # Check for specific stage failures
        stages = execution.get("stages", {})
        for stage_name, stage_data in stages.items():
            if stage_data.get("status") == "failure":
                recommendations.append(
                    f"Investigate failure in {stage_data.get('name', stage_name)} stage"
                )
            elif stage_data.get("retry_count", 0) > 0:
                recommendations.append(
                    f"Improve reliability of {stage_data.get('name', stage_name)} stage to reduce retries"
                )

        # Check for missing coverage
        for component, covered in self.report_data.get(
            "component_coverage", {}
        ).items():
            if not covered:
                recommendations.append(f"Add test coverage for {component}")

        # Add recommendations to report data
        self.report_data["recommendations"] = recommendations


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="E2E Pipeline Report Generator")
    parser.add_argument("--execution-id", help="Specific execution ID to report on")
    parser.add_argument("--history-file", help="Path to execution history JSON file")
    parser.add_argument("--output", "-o", help="Output file for the report")
    parser.add_argument(
        "--detailed", action="store_true", help="Generate a detailed report"
    )
    parser.add_argument("--trend", action="store_true", help="Generate a trend report")
    parser.add_argument(
        "--num-executions",
        type=int,
        default=10,
        help="Number of executions for trend report",
    )

    args = parser.parse_args()

    generator = ReportGenerator(args.execution_id, args.history_file)

    if args.trend:
        generator.generate_trend_report(args.num_executions, args.output)
    elif args.detailed:
        generator.generate_detailed_report(args.output)
    else:
        generator.generate_summary_report(args.output)

    if not args.output:
        pass


if __name__ == "__main__":
    main()
