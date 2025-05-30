#!/usr/bin/env python3
"""
Comprehensive E2E Pipeline Result Validation and Reporting

This module provides robust validation and reporting capabilities for E2E pipeline executions,
including result validation, metrics tracking, and report generation for various stakeholders.
"""

import csv
import datetime
import json
import logging
import os
import smtplib
import sys
import tempfile
from collections import defaultdict
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import matplotlib.pyplot as plt

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

from scripts.e2e.execution_logger import ExecutionTracker
from scripts.e2e.failure_analyzer import FailureAnalyzer

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(console_handler)


class ReportType:
    """Types of reports that can be generated."""

    EXECUTIVE_SUMMARY = "executive_summary"
    TECHNICAL_DETAIL = "technical_detail"
    TREND_ANALYSIS = "trend_analysis"
    ISSUE_REPORT = "issue_report"
    TEST_COVERAGE = "test_coverage"
    PERFORMANCE_METRICS = "performance_metrics"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"


class OutputFormat:
    """Output formats for reports."""

    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    CONSOLE = "console"
    EMAIL = "email"
    SLACK = "slack"


class MetricsCalculator:
    """
    Calculates various metrics from pipeline execution data.
    """

    def __init__(self):
        """
        Initialize the metrics calculator.
        """
        self.tracker = ExecutionTracker()

    def calculate_success_rate(self, num_executions: int = 10) -> float:
        """
        Calculate the overall success rate of recent executions.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Success rate as a percentage
        """
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return 0.0

        success_count = sum(1 for e in executions if e.get("status") == "success")
        return (success_count / len(executions)) * 100

    def calculate_stage_success_rates(
        self, num_executions: int = 10
    ) -> dict[str, float]:
        """
        Calculate success rates for each pipeline stage.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Dictionary mapping stage names to success rates
        """
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return {}

        # Count stage successes and total runs
        stage_success = defaultdict(int)
        stage_total = defaultdict(int)

        for execution in executions:
            stages = execution.get("stages", {})

            for stage_name, stage_data in stages.items():
                stage_total[stage_name] += 1
                if stage_data.get("status") == "success":
                    stage_success[stage_name] += 1

        # Calculate success rates
        return {
            stage: (
                (stage_success[stage] / stage_total[stage]) * 100
                if stage_total[stage] > 0
                else 0.0
            )
            for stage in stage_total
        }

    def calculate_average_duration(self, num_executions: int = 10) -> float:
        """
        Calculate the average duration of recent executions.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Average duration in seconds
        """
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return 0.0

        durations = [e.get("duration", 0) for e in executions]
        return sum(durations) / len(durations) if durations else 0.0

    def calculate_stage_average_durations(
        self, num_executions: int = 10
    ) -> dict[str, float]:
        """
        Calculate average durations for each pipeline stage.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Dictionary mapping stage names to average durations
        """
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return {}

        # Collect stage durations
        stage_durations = defaultdict(list)

        for execution in executions:
            stages = execution.get("stages", {})

            for stage_name, stage_data in stages.items():
                duration = stage_data.get("duration", 0)
                stage_durations[stage_name].append(duration)

        # Calculate average durations
        return {
            stage: sum(durations) / len(durations) if durations else 0.0
            for stage, durations in stage_durations.items()
        }

    def calculate_failure_counts(self, num_executions: int = 10) -> dict[str, int]:
        """
        Calculate failure counts by category.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Dictionary mapping failure categories to counts
        """
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return {}

        # Count failures by category
        category_counts = defaultdict(int)

        for execution in executions:
            failures = execution.get("failures", [])

            for failure in failures:
                category = failure.get("category", "unknown")
                category_counts[category] += 1

        return dict(category_counts)

    def calculate_retry_rates(self, num_executions: int = 10) -> dict[str, float]:
        """
        Calculate retry rates for each pipeline stage.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Dictionary mapping stage names to retry rates
        """
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return {}

        # Count retries and total runs
        stage_retries = defaultdict(int)
        stage_total = defaultdict(int)

        for execution in executions:
            stages = execution.get("stages", {})

            for stage_name, stage_data in stages.items():
                stage_total[stage_name] += 1
                retry_count = stage_data.get("retry_count", 0)

                if retry_count > 0:
                    stage_retries[stage_name] += 1

        # Calculate retry rates
        return {
            stage: (
                (stage_retries[stage] / stage_total[stage]) * 100
                if stage_total[stage] > 0
                else 0.0
            )
            for stage in stage_total
        }


class ResultValidator:
    """
    Validates E2E pipeline execution results against requirements and expected outcomes.
    """

    def __init__(self, requirements_file: Optional[str] = None):
        """
        Initialize the result validator.

        Args:
            requirements_file: Path to a JSON file containing requirements
        """
        self.requirements_file = requirements_file or str(
            project_root / "scripts" / "e2e" / "requirements.json"
        )
        self.requirements = self._load_requirements()
        self.tracker = ExecutionTracker()

    def _load_requirements(self) -> dict[str, Any]:
        """
        Load requirements from the requirements file.

        Returns:
            Dictionary containing requirements data
        """
        if not os.path.exists(self.requirements_file):
            logger.warning(f"Requirements file not found: {self.requirements_file}")
            return self._create_default_requirements()

        try:
            with open(self.requirements_file) as f:
                requirements_data = json.load(f)
                logger.info(f"Loaded requirements from {self.requirements_file}")
                return requirements_data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load requirements: {e}")
            return self._create_default_requirements()

    def _create_default_requirements(self) -> dict[str, Any]:
        """
        Create default requirements.

        Returns:
            Dictionary containing default requirements
        """
        default_requirements = {
            "test_coverage": {
                "required_stages": [
                    "preflight",
                    "scrape",
                    "screenshot",
                    "mockup",
                    "personalize",
                    "render",
                    "email",
                ],
                "critical_stages": ["preflight", "scrape", "email"],
                "minimum_success_rate": 90.0,
            },
            "performance": {
                "max_duration_seconds": {
                    "total": 900,  # 15 minutes
                    "preflight": 60,
                    "scrape": 300,
                    "screenshot": 120,
                    "mockup": 180,
                    "personalize": 60,
                    "render": 60,
                    "email": 60,
                },
                "max_retry_count": 2,
            },
            "result_validation": {
                "required_outputs": {
                    "scrape": ["data/scraped_*.json"],
                    "screenshot": ["screenshots/*.png"],
                    "mockup": ["mockups/*.png"],
                    "render": ["emails/*.html"],
                    "email": ["sent_emails.json"],
                }
            },
        }

        logger.info("Created default requirements")

        # Save default requirements
        try:
            os.makedirs(os.path.dirname(self.requirements_file), exist_ok=True)
            with open(self.requirements_file, "w") as f:
                json.dump(default_requirements, f, indent=2)
                logger.info(f"Saved default requirements to {self.requirements_file}")
        except OSError as e:
            logger.error(f"Failed to save default requirements: {e}")

        return default_requirements

    def validate_test_coverage(
        self, execution_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Validate test coverage against requirements.

        Args:
            execution_id: Optional execution ID to validate, or None for latest

        Returns:
            Validation results
        """
        # Get execution data
        execution = None
        if execution_id:
            execution = self.tracker.get_execution(execution_id)
        else:
            recent = self.tracker.get_recent_executions(1)
            if recent:
                execution = recent[0]

        if not execution:
            return {
                "valid": False,
                "message": "No execution data found",
                "missing_stages": [],
                "executed_stages": [],
                "failed_stages": [],
                "success_rate": 0.0,
            }

        # Get required stages
        required_stages = self.requirements.get("test_coverage", {}).get(
            "required_stages", []
        )
        critical_stages = self.requirements.get("test_coverage", {}).get(
            "critical_stages", []
        )
        minimum_success_rate = self.requirements.get("test_coverage", {}).get(
            "minimum_success_rate", 90.0
        )

        # Get executed stages
        executed_stages = []
        failed_stages = []
        stages_data = execution.get("stages", {})

        for stage_name, stage_data in stages_data.items():
            executed_stages.append(stage_name)
            if stage_data.get("status") != "success":
                failed_stages.append(stage_name)

        # Check for missing stages
        missing_stages = [
            stage for stage in required_stages if stage not in executed_stages
        ]

        # Check for critical stage failures
        critical_failures = [
            stage for stage in failed_stages if stage in critical_stages
        ]

        # Calculate success rate
        total_required = len(required_stages)
        successful_required = len(
            [
                stage
                for stage in required_stages
                if stage in executed_stages and stage not in failed_stages
            ]
        )
        success_rate = (
            (successful_required / total_required) * 100 if total_required > 0 else 0.0
        )

        # Validate
        valid = (
            len(missing_stages) == 0
            and len(critical_failures) == 0
            and success_rate >= minimum_success_rate
        )

        return {
            "valid": valid,
            "message": "Test coverage validation completed",
            "missing_stages": missing_stages,
            "critical_failures": critical_failures,
            "executed_stages": executed_stages,
            "failed_stages": failed_stages,
            "success_rate": success_rate,
            "minimum_success_rate": minimum_success_rate,
        }

    def validate_performance(
        self, execution_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Validate performance metrics against requirements.

        Args:
            execution_id: Optional execution ID to validate, or None for latest

        Returns:
            Validation results
        """
        # Get execution data
        execution = None
        if execution_id:
            execution = self.tracker.get_execution(execution_id)
        else:
            recent = self.tracker.get_recent_executions(1)
            if recent:
                execution = recent[0]

        if not execution:
            return {
                "valid": False,
                "message": "No execution data found",
                "performance_issues": [],
            }

        # Get performance requirements
        max_duration = self.requirements.get("performance", {}).get(
            "max_duration_seconds", {}
        )
        max_retry_count = self.requirements.get("performance", {}).get(
            "max_retry_count", 2
        )

        # Validate total duration
        total_duration = execution.get("duration", 0)
        max_total_duration = max_duration.get("total", 900)  # Default 15 min

        performance_issues = []

        if total_duration > max_total_duration:
            performance_issues.append(
                {
                    "type": "total_duration",
                    "message": f"Total execution time ({total_duration}s) exceeds maximum ({max_total_duration}s)",
                    "actual": total_duration,
                    "limit": max_total_duration,
                }
            )

        # Validate stage durations
        stages_data = execution.get("stages", {})

        for stage_name, stage_data in stages_data.items():
            # Check duration
            stage_duration = stage_data.get("duration", 0)
            max_stage_duration = max_duration.get(stage_name, 300)  # Default 5 min

            if stage_duration > max_stage_duration:
                performance_issues.append(
                    {
                        "type": "stage_duration",
                        "stage": stage_name,
                        "message": f"Stage {stage_name} execution time ({stage_duration}s) exceeds maximum ({max_stage_duration}s)",
                        "actual": stage_duration,
                        "limit": max_stage_duration,
                    }
                )

            # Check retry count
            retry_count = stage_data.get("retry_count", 0)

            if retry_count > max_retry_count:
                performance_issues.append(
                    {
                        "type": "retry_count",
                        "stage": stage_name,
                        "message": f"Stage {stage_name} retry count ({retry_count}) exceeds maximum ({max_retry_count})",
                        "actual": retry_count,
                        "limit": max_retry_count,
                    }
                )

        # Validate
        valid = len(performance_issues) == 0

        return {
            "valid": valid,
            "message": "Performance validation completed",
            "performance_issues": performance_issues,
        }

    def validate_outputs(self, execution_id: Optional[str] = None) -> dict[str, Any]:
        """
        Validate the presence of required output files.

        Args:
            execution_id: Optional execution ID to validate, or None for latest

        Returns:
            Validation results
        """
        # Get required outputs
        required_outputs = self.requirements.get("result_validation", {}).get(
            "required_outputs", {}
        )

        # For each required output, check if the file exists
        missing_outputs = []

        for stage_name, patterns in required_outputs.items():
            for pattern in patterns:
                # Resolve the pattern to an absolute path
                absolute_pattern = str(project_root / pattern)

                # Use glob to find matching files
                import glob

                matching_files = glob.glob(absolute_pattern)

                if not matching_files:
                    missing_outputs.append(
                        {
                            "stage": stage_name,
                            "pattern": pattern,
                            "message": f"No files found matching pattern {pattern} for stage {stage_name}",
                        }
                    )

        # Validate
        valid = len(missing_outputs) == 0

        return {
            "valid": valid,
            "message": "Output validation completed",
            "missing_outputs": missing_outputs,
        }

    def validate_execution(self, execution_id: Optional[str] = None) -> dict[str, Any]:
        """
        Perform comprehensive validation of an execution.

        Args:
            execution_id: Optional execution ID to validate, or None for latest

        Returns:
            Comprehensive validation results
        """
        # Get execution data
        execution = None
        if execution_id:
            execution = self.tracker.get_execution(execution_id)
        else:
            recent = self.tracker.get_recent_executions(1)
            if recent:
                execution = recent[0]
                execution_id = execution.get("execution_id", "unknown")

        if not execution:
            return {
                "valid": False,
                "message": "No execution data found",
                "execution_id": execution_id or "unknown",
                "validations": {},
            }

        # Perform individual validations
        coverage_results = self.validate_test_coverage(execution_id)
        performance_results = self.validate_performance(execution_id)
        output_results = self.validate_outputs(execution_id)

        # Combine results
        valid = (
            coverage_results.get("valid", False)
            and performance_results.get("valid", False)
            and output_results.get("valid", False)
        )

        return {
            "valid": valid,
            "message": "Execution validation completed",
            "execution_id": execution_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "validations": {
                "test_coverage": coverage_results,
                "performance": performance_results,
                "outputs": output_results,
            },
        }


class ReportGenerator:
    """
    Generates various types of reports for E2E pipeline executions.
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the report generator.

        Args:
            output_dir: Directory to save reports to
        """
        self.output_dir = output_dir or str(project_root / "reports")
        self.tracker = ExecutionTracker()
        self.validator = ResultValidator()
        self.metrics = MetricsCalculator()
        self.analyzer = FailureAnalyzer()

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_report(
        self,
        report_type: str,
        output_format: str,
        execution_id: Optional[str] = None,
        num_executions: int = 10,
    ) -> str:
        """
        Generate a report of the specified type and format.

        Args:
            report_type: Type of report to generate
            output_format: Format of the report
            execution_id: Optional execution ID to report on, or None for latest
            num_executions: Number of recent executions to analyze for trend reports

        Returns:
            Path to the generated report file
        """
        # Get execution data
        execution = None
        if execution_id:
            execution = self.tracker.get_execution(execution_id)
        else:
            recent = self.tracker.get_recent_executions(1)
            if recent:
                execution = recent[0]
                execution_id = execution.get("execution_id", "unknown")

        # Generate report content based on type
        if report_type == ReportType.EXECUTIVE_SUMMARY:
            content = self._generate_executive_summary(execution_id, num_executions)
        elif report_type == ReportType.TECHNICAL_DETAIL:
            content = self._generate_technical_detail(execution_id)
        elif report_type == ReportType.TREND_ANALYSIS:
            content = self._generate_trend_analysis(num_executions)
        elif report_type == ReportType.ISSUE_REPORT:
            content = self._generate_issue_report(execution_id)
        elif report_type == ReportType.TEST_COVERAGE:
            content = self._generate_test_coverage_report(execution_id)
        elif report_type == ReportType.PERFORMANCE_METRICS:
            content = self._generate_performance_metrics(num_executions)
        elif report_type == ReportType.DAILY_SUMMARY:
            content = self._generate_daily_summary()
        elif report_type == ReportType.WEEKLY_SUMMARY:
            content = self._generate_weekly_summary()
        else:
            raise ValueError(f"Unsupported report type: {report_type}")

        # Format report based on output format
        if output_format == OutputFormat.HTML:
            formatted_content = self._format_as_html(content, report_type)
            extension = "html"
        elif output_format == OutputFormat.MARKDOWN:
            formatted_content = self._format_as_markdown(content, report_type)
            extension = "md"
        elif output_format == OutputFormat.JSON:
            formatted_content = json.dumps(content, indent=2)
            extension = "json"
        elif output_format == OutputFormat.CSV:
            formatted_content = self._format_as_csv(content, report_type)
            extension = "csv"
        elif output_format == OutputFormat.CONSOLE:
            formatted_content = self._format_as_console(content, report_type)
            return None
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

        # Save to file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_{timestamp}.{extension}"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w") as f:
            f.write(formatted_content)

        return filepath

    def _generate_executive_summary(
        self, execution_id: Optional[str], num_executions: int
    ) -> dict[str, Any]:
        """
        Generate an executive summary report.

        Args:
            execution_id: Optional execution ID to report on
            num_executions: Number of recent executions to analyze

        Returns:
            Report data as a dictionary
        """
        # Get validation results
        validation_results = self.validator.validate_execution(execution_id)

        # Get metrics
        success_rate = self.metrics.calculate_success_rate(num_executions)
        avg_duration = self.metrics.calculate_average_duration(num_executions)
        failure_counts = self.metrics.calculate_failure_counts(num_executions)

        # Get recent trend
        trend_data = []
        recent_executions = self.tracker.get_recent_executions(num_executions)

        for execution in recent_executions:
            status = execution.get("status", "unknown")
            timestamp = execution.get("start_time", "")
            duration = execution.get("duration", 0)

            trend_data.append(
                {
                    "execution_id": execution.get("execution_id", "unknown"),
                    "status": status,
                    "timestamp": timestamp,
                    "duration": duration,
                }
            )

        # Generate summary
        return {
            "title": "E2E Pipeline Executive Summary",
            "timestamp": datetime.datetime.now().isoformat(),
            "period": f"Last {num_executions} executions",
            "overall_health": {
                "success_rate": success_rate,
                "average_duration": avg_duration,
                "status": (
                    "Good"
                    if success_rate >= 90
                    else "Warning" if success_rate >= 75 else "Critical"
                ),
            },
            "latest_execution": {
                "execution_id": validation_results.get("execution_id", "unknown"),
                "status": (
                    "Success" if validation_results.get("valid", False) else "Failure"
                ),
                "issues": self._count_validation_issues(validation_results),
            },
            "failure_distribution": failure_counts,
            "trend": trend_data,
        }

    def _count_validation_issues(self, validation_results: dict[str, Any]) -> int:
        """
        Count the number of validation issues in validation results.

        Args:
            validation_results: Validation results dictionary

        Returns:
            Number of validation issues
        """
        count = 0
        validations = validation_results.get("validations", {})

        # Count test coverage issues
        coverage = validations.get("test_coverage", {})
        count += len(coverage.get("missing_stages", []))
        count += len(coverage.get("critical_failures", []))
        count += len(coverage.get("failed_stages", []))

        # Count performance issues
        performance = validations.get("performance", {})
        count += len(performance.get("performance_issues", []))

        # Count output issues
        outputs = validations.get("outputs", {})
        count += len(outputs.get("missing_outputs", []))

        return count

    def _format_as_html(self, content: dict[str, Any], report_type: str) -> str:
        """
        Format report content as HTML.

        Args:
            content: Report content as a dictionary
            report_type: Type of report

        Returns:
            HTML formatted report
        """
        # Basic HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{content.get('title', 'E2E Pipeline Report')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        .good {{ color: green; }}
        .warning {{ color: orange; }}
        .critical {{ color: red; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .section {{ margin-bottom: 30px; }}
    </style>
</head>
<body>
    <h1>{content.get('title', 'E2E Pipeline Report')}</h1>
    <p>Generated on: {content.get('timestamp', datetime.datetime.now().isoformat())}</p>
"""

        # Add report-specific content
        if report_type == ReportType.EXECUTIVE_SUMMARY:
            html += self._executive_summary_to_html(content)
        elif report_type == ReportType.TECHNICAL_DETAIL:
            html += self._technical_detail_to_html(content)
        elif report_type == ReportType.TREND_ANALYSIS:
            html += self._trend_analysis_to_html(content)
        else:
            # Generic dictionary to HTML converter
            html += "<h2>Report Data</h2>"
            html += self._dict_to_html_table(content)

        # Close HTML
        html += "\n</body>\n</html>"

        return html

    def _executive_summary_to_html(self, content: dict[str, Any]) -> str:
        """
        Format executive summary as HTML.

        Args:
            content: Report content

        Returns:
            HTML formatted content
        """
        html = "<div class='section'>"
        html += "<h2>Overall Health</h2>"

        health = content.get("overall_health", {})
        status = health.get("status", "Unknown")
        status_class = (
            "good"
            if status == "Good"
            else "warning" if status == "Warning" else "critical"
        )

        html += f"<p>Status: <span class='{status_class}'>{status}</span></p>"
        html += f"<p>Success Rate: {health.get('success_rate', 0):.1f}%</p>"
        html += (
            f"<p>Average Duration: {health.get('average_duration', 0):.1f} seconds</p>"
        )
        html += "</div>"

        # Latest execution
        html += "<div class='section'>"
        html += "<h2>Latest Execution</h2>"
        latest = content.get("latest_execution", {})
        html += f"<p>Execution ID: {latest.get('execution_id', 'Unknown')}</p>"
        html += f"<p>Status: {latest.get('status', 'Unknown')}</p>"
        html += f"<p>Issues: {latest.get('issues', 0)}</p>"
        html += "</div>"

        # Failure distribution
        html += "<div class='section'>"
        html += "<h2>Failure Distribution</h2>"
        failures = content.get("failure_distribution", {})

        if failures:
            html += "<table>"
            html += "<tr><th>Category</th><th>Count</th></tr>"

            for category, count in failures.items():
                html += f"<tr><td>{category}</td><td>{count}</td></tr>"

            html += "</table>"
        else:
            html += "<p>No failures recorded.</p>"
        html += "</div>"

        # Recent trend
        html += "<div class='section'>"
        html += "<h2>Recent Executions</h2>"
        trend = content.get("trend", [])

        if trend:
            html += "<table>"
            html += "<tr><th>Execution ID</th><th>Status</th><th>Timestamp</th><th>Duration (s)</th></tr>"

            for execution in trend:
                status_class = (
                    "good" if execution.get("status") == "success" else "critical"
                )
                html += "<tr>"
                html += f"<td>{execution.get('execution_id', 'Unknown')}</td>"
                html += f"<td class='{status_class}'>{execution.get('status', 'Unknown')}</td>"
                html += f"<td>{execution.get('timestamp', '')}</td>"
                html += f"<td>{execution.get('duration', 0):.1f}</td>"
                html += "</tr>"

            html += "</table>"
        else:
            html += "<p>No execution data available.</p>"
        html += "</div>"

        return html

    def _dict_to_html_table(self, data: dict[str, Any], nested: bool = False) -> str:
        """
        Convert a dictionary to an HTML table.

        Args:
            data: Dictionary to convert
            nested: Whether this is a nested dictionary

        Returns:
            HTML table representation of the dictionary
        """
        if not data:
            return "<p>No data available.</p>"

        html = "<table>" if not nested else ""
        html += "<tr><th>Key</th><th>Value</th></tr>"

        for key, value in data.items():
            html += "<tr>"
            html += f"<td>{key}</td>"

            if isinstance(value, dict):
                html += f"<td>{self._dict_to_html_table(value, True)}</td>"
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    # List of dictionaries
                    html += "<td><table>"
                    # Create headers
                    headers = set()
                    for item in value:
                        headers.update(item.keys())

                    html += "<tr>"
                    for header in headers:
                        html += f"<th>{header}</th>"
                    html += "</tr>"

                    # Add rows
                    for item in value:
                        html += "<tr>"
                        for header in headers:
                            html += f"<td>{item.get(header, '')}</td>"
                        html += "</tr>"

                    html += "</table></td>"
                else:
                    # Simple list
                    html += f"<td>{', '.join(str(x) for x in value)}</td>"
            else:
                html += f"<td>{value}</td>"

            html += "</tr>"

        html += "</table>" if not nested else ""
        return html

    def _format_as_markdown(self, content: dict[str, Any], report_type: str) -> str:
        """
        Format report content as Markdown.

        Args:
            content: Report content as a dictionary
            report_type: Type of report

        Returns:
            Markdown formatted report
        """
        # Basic Markdown template
        md = f"# {content.get('title', 'E2E Pipeline Report')}\n\n"
        md += f"Generated on: {content.get('timestamp', datetime.datetime.now().isoformat())}\n\n"

        # Add report-specific content
        if report_type == ReportType.EXECUTIVE_SUMMARY:
            md += self._executive_summary_to_markdown(content)
        elif report_type == ReportType.TECHNICAL_DETAIL:
            md += self._technical_detail_to_markdown(content)
        elif report_type == ReportType.TREND_ANALYSIS:
            md += self._trend_analysis_to_markdown(content)
        else:
            # Generic dictionary to Markdown converter
            md += "## Report Data\n\n"
            md += self._dict_to_markdown(content)

        return md

    def _executive_summary_to_markdown(self, content: dict[str, Any]) -> str:
        """
        Format executive summary as Markdown.

        Args:
            content: Report content

        Returns:
            Markdown formatted content
        """
        md = "## Overall Health\n\n"

        health = content.get("overall_health", {})
        status = health.get("status", "Unknown")

        md += f"Status: **{status}**\n\n"
        md += f"Success Rate: {health.get('success_rate', 0):.1f}%\n\n"
        md += f"Average Duration: {health.get('average_duration', 0):.1f} seconds\n\n"

        # Latest execution
        md += "## Latest Execution\n\n"
        latest = content.get("latest_execution", {})
        md += f"Execution ID: {latest.get('execution_id', 'Unknown')}\n\n"
        md += f"Status: {latest.get('status', 'Unknown')}\n\n"
        md += f"Issues: {latest.get('issues', 0)}\n\n"

        # Failure distribution
        md += "## Failure Distribution\n\n"
        failures = content.get("failure_distribution", {})

        if failures:
            md += "| Category | Count |\n"
            md += "|----------|-------|\n"

            for category, count in failures.items():
                md += f"| {category} | {count} |\n"

            md += "\n"
        else:
            md += "No failures recorded.\n\n"

        # Recent trend
        md += "## Recent Executions\n\n"
        trend = content.get("trend", [])

        if trend:
            md += "| Execution ID | Status | Timestamp | Duration (s) |\n"
            md += "|--------------|--------|-----------|--------------|\n"

            for execution in trend:
                md += f"| {execution.get('execution_id', 'Unknown')} "
                md += f"| {execution.get('status', 'Unknown')} "
                md += f"| {execution.get('timestamp', '')} "
                md += f"| {execution.get('duration', 0):.1f} |\n"

            md += "\n"
        else:
            md += "No execution data available.\n\n"

        return md

    def _technical_detail_to_markdown(self, content: dict[str, Any]) -> str:
        """
        Format technical detail report as Markdown.

        Args:
            content: Report content

        Returns:
            Markdown formatted content
        """
        md = "## Technical Details\n\n"

        # Execution details
        execution = content.get("execution_details", {})
        if execution:
            md += "### Execution Information\n\n"
            md += f"- **Execution ID**: {execution.get('execution_id', 'Unknown')}\n"
            md += f"- **Status**: {execution.get('status', 'Unknown')}\n"
            md += f"- **Start Time**: {execution.get('start_time', 'Unknown')}\n"
            md += f"- **End Time**: {execution.get('end_time', 'Unknown')}\n"
            md += f"- **Duration**: {execution.get('duration', 0)} seconds\n\n"

        # Stage details
        stages = content.get("stage_details", {})
        if stages:
            md += "### Stage Details\n\n"
            for stage_name, stage_data in stages.items():
                md += f"#### {stage_name}\n\n"
                md += f"- **Status**: {stage_data.get('status', 'Unknown')}\n"
                md += f"- **Duration**: {stage_data.get('duration', 0)} seconds\n"
                if "error" in stage_data:
                    md += f"- **Error**: {stage_data['error']}\n"
                md += "\n"

        # Failures
        failures = content.get("failures", [])
        if failures:
            md += "### Failures\n\n"
            for failure in failures:
                md += f"- **{failure.get('name', 'Unknown')}**: {failure.get('description', '')}\n"
            md += "\n"

        # Validations
        validations = content.get("validations", {})
        if validations:
            md += "### Validation Results\n\n"
            md += self._dict_to_markdown(validations, level=1)

        return md

    def _trend_analysis_to_markdown(self, content: dict[str, Any]) -> str:
        """
        Format trend analysis report as Markdown.

        Args:
            content: Report content

        Returns:
            Markdown formatted content
        """
        md = "## Trend Analysis\n\n"

        # Overall metrics
        overall = content.get("overall_metrics", {})
        if overall:
            md += "### Overall Metrics\n\n"
            md += f"- **Success Rate**: {overall.get('success_rate', 0):.1f}%\n"
            md += f"- **Average Duration**: {overall.get('average_duration', 0):.1f} seconds\n"
            md += f"- **Trend**: {overall.get('trend', 'Unknown')}\n\n"

        # Stage metrics
        stage_metrics = content.get("stage_metrics", {})
        if stage_metrics:
            md += "### Stage Performance\n\n"
            success_rates = stage_metrics.get("success_rates", {})
            avg_durations = stage_metrics.get("average_durations", {})
            retry_rates = stage_metrics.get("retry_rates", {})
            reliability = stage_metrics.get("reliability", {})

            stage_names = set()
            stage_names.update(success_rates.keys())
            stage_names.update(avg_durations.keys())
            stage_names.update(retry_rates.keys())
            stage_names.update(reliability.keys())

            if stage_names:
                md += "| Stage | Success Rate | Avg Duration | Retry Rate | Reliability |\n"
                md += "|-------|-------------|--------------|------------|-------------|\n"

                for stage_name in sorted(stage_names):
                    md += f"| {stage_name} "
                    md += f"| {success_rates.get(stage_name, 0):.1f}% "
                    md += f"| {avg_durations.get(stage_name, 0):.1f}s "
                    md += f"| {retry_rates.get(stage_name, 0):.1f}% "
                    md += f"| {reliability.get(stage_name, 'Unknown')} |\n"
                md += "\n"

        # Failure patterns
        failure_patterns = content.get("failure_distribution", {})
        if failure_patterns:
            md += "### Failure Patterns\n\n"
            md += "| Category | Count | Percentage |\n"
            md += "|----------|-------|------------|\n"

            total_failures = sum(failure_patterns.values())
            for category, count in failure_patterns.items():
                percentage = (count / total_failures * 100) if total_failures > 0 else 0
                md += f"| {category} | {count} | {percentage:.1f}% |\n"
            md += "\n"

        # Execution trend
        execution_trend = content.get("execution_trend", [])
        if execution_trend:
            md += "### Recent Execution Trend\n\n"
            md += "| Date | Success Rate | Avg Duration | Total Runs |\n"
            md += "|------|-------------|--------------|------------|\n"

            for trend_point in execution_trend[:10]:  # Show last 10 data points
                md += f"| {trend_point.get('start_time', 'Unknown')[:10]} "
                success_rate = (trend_point.get("status") == "success") * 100
                md += f"| {success_rate:.0f}% "
                md += f"| {trend_point.get('duration', 0):.1f}s "
                md += "| 1 |\n"
            md += "\n"

        # Failure analysis and recurring patterns
        failure_analysis = content.get("failure_analysis", {})
        if failure_analysis:
            recurring_patterns = failure_analysis.get("recurring_patterns", [])
            if recurring_patterns:
                md += "### Recurring Patterns\n\n"
                for pattern in recurring_patterns:
                    md += f"- {pattern}\n"
                md += "\n"

            failure_counts = failure_analysis.get("failure_counts", {})
            if failure_counts:
                md += "### Failure Categories\n\n"
                md += "| Category | Count |\n"
                md += "|----------|-------|\n"
                for category, count in failure_counts.items():
                    md += f"| {category} | {count} |\n"
                md += "\n"

        return md

    def _dict_to_markdown(self, data: dict[str, Any], level: int = 0) -> str:
        """
        Convert a dictionary to Markdown format.

        Args:
            data: Dictionary to convert
            level: Current heading level

        Returns:
            Markdown representation of the dictionary
        """
        if not data:
            return "No data available.\n\n"

        md = ""
        prefix = "#" * (level + 2)  # Start with ## for level 0

        for key, value in data.items():
            if isinstance(value, dict):
                md += f"{prefix} {key}\n\n"
                md += self._dict_to_markdown(value, level + 1)
            elif isinstance(value, list):
                md += f"{prefix} {key}\n\n"

                if value and isinstance(value[0], dict):
                    # List of dictionaries
                    headers = set()
                    for item in value:
                        headers.update(item.keys())

                    # Create table header
                    md += "| " + " | ".join(headers) + " |\n"
                    md += "| " + " | ".join(["-" * len(h) for h in headers]) + " |\n"

                    # Create table rows
                    for item in value:
                        row = ""
                        for header in headers:
                            row += f"| {item.get(header, '')} "
                        row += "|\n"
                        md += row

                    md += "\n"
                else:
                    # Simple list
                    for item in value:
                        md += f"- {item}\n"
                    md += "\n"
            else:
                md += f"{prefix} {key}\n\n{value}\n\n"

        return md

    def _format_as_csv(self, content: dict[str, Any], report_type: str) -> str:
        """
        Format report content as CSV.

        Args:
            content: Report content as a dictionary
            report_type: Type of report

        Returns:
            CSV formatted report
        """
        # Only certain report types make sense as CSV
        if report_type in [ReportType.TREND_ANALYSIS, ReportType.PERFORMANCE_METRICS]:
            # These contain tabular data suitable for CSV
            return self._tabular_data_to_csv(content)
        else:
            # For other reports, just create a flat key-value CSV
            return self._dict_to_csv(content)

    def _tabular_data_to_csv(self, content: dict[str, Any]) -> str:
        """
        Convert tabular data to CSV format.

        Args:
            content: Report content with tabular data

        Returns:
            CSV formatted data
        """
        # Find the first list of dictionaries in the content
        for _key, value in content.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                # This is a table we can convert to CSV
                import csv
                import io

                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=value[0].keys())
                writer.writeheader()
                writer.writerows(value)

                return output.getvalue()

        # Fallback to flat CSV if no tabular data found
        return self._dict_to_csv(content)

    def _dict_to_csv(self, data: dict[str, Any]) -> str:
        """
        Convert a dictionary to flat CSV format.

        Args:
            data: Dictionary to convert

        Returns:
            CSV formatted data
        """
        import io

        # Flatten the dictionary
        flat_data = []

        def flatten_dict(d, prefix=""):
            for key, value in d.items():
                new_key = f"{prefix}.{key}" if prefix else key

                if isinstance(value, dict):
                    flatten_dict(value, new_key)
                elif isinstance(value, list):
                    # Skip lists for simplicity
                    pass
                else:
                    flat_data.append({"Key": new_key, "Value": value})

        flatten_dict(data)

        # Convert to CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["Key", "Value"])
        writer.writeheader()
        writer.writerows(flat_data)

        return output.getvalue()

    def _format_as_console(self, content: dict[str, Any], report_type: str) -> str:
        """
        Format report content for console output.

        Args:
            content: Report content as a dictionary
            report_type: Type of report

        Returns:
            Console formatted report
        """
        # For console output, use a similar format to Markdown but with ANSI colors
        output = f"=== {content.get('title', 'E2E Pipeline Report')} ===\n\n"
        output += f"Generated on: {content.get('timestamp', datetime.datetime.now().isoformat())}\n\n"

        if report_type == ReportType.EXECUTIVE_SUMMARY:
            # Overall health section
            output += "=== Overall Health ===\n\n"

            health = content.get("overall_health", {})
            status = health.get("status", "Unknown")

            # Add color based on status
            status_colored = status
            if status == "Good":
                status_colored = f"\033[32m{status}\033[0m"  # Green
            elif status == "Warning":
                status_colored = f"\033[33m{status}\033[0m"  # Yellow
            elif status == "Critical":
                status_colored = f"\033[31m{status}\033[0m"  # Red

            output += f"Status: {status_colored}\n"
            output += f"Success Rate: {health.get('success_rate', 0):.1f}%\n"
            output += (
                f"Average Duration: {health.get('average_duration', 0):.1f} seconds\n\n"
            )

            # Latest execution
            output += "=== Latest Execution ===\n\n"
            latest = content.get("latest_execution", {})
            output += f"Execution ID: {latest.get('execution_id', 'Unknown')}\n"
            output += f"Status: {latest.get('status', 'Unknown')}\n"
            output += f"Issues: {latest.get('issues', 0)}\n\n"

            # Failure distribution
            output += "=== Failure Distribution ===\n\n"
            failures = content.get("failure_distribution", {})

            if failures:
                max_category_len = max(len(str(k)) for k in failures)

                for category, count in failures.items():
                    output += f"{category:{max_category_len}}: {count}\n"

                output += "\n"
            else:
                output += "No failures recorded.\n\n"

            # Recent trend
            output += "=== Recent Executions ===\n\n"
            trend = content.get("trend", [])

            if trend:
                # Format as a table with fixed width columns
                output += f"{'Execution ID':<20} {'Status':<10} {'Timestamp':<24} {'Duration (s)':<12}\n"
                output += f"{'-'*20} {'-'*10} {'-'*24} {'-'*12}\n"

                for execution in trend:
                    status = execution.get("status", "Unknown")
                    status_colored = status

                    if status == "success":
                        status_colored = f"\033[32m{status}\033[0m"  # Green
                    elif status == "failure":
                        status_colored = f"\033[31m{status}\033[0m"  # Red

                    output += f"{execution.get('execution_id', 'Unknown'):<20} "
                    output += f"{status_colored:<10} "
                    output += f"{execution.get('timestamp', ''):<24} "
                    output += f"{execution.get('duration', 0):.1f}\n"

                output += "\n"
            else:
                output += "No execution data available.\n\n"
        else:
            # For other report types, just use a simple key-value format
            output += self._dict_to_console(content)

        return output

    def _dict_to_console(self, data: dict[str, Any], indent: int = 0) -> str:
        """
        Convert a dictionary to console output with indentation.

        Args:
            data: Dictionary to convert
            indent: Current indentation level

        Returns:
            Console formatted output
        """
        if not data:
            return "No data available.\n\n"

        output = ""
        indent_str = "  " * indent

        for key, value in data.items():
            if isinstance(value, dict):
                output += f"{indent_str}{key}:\n"
                output += self._dict_to_console(value, indent + 1)
            elif isinstance(value, list):
                output += f"{indent_str}{key}:\n"

                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        output += f"{indent_str}  [{i}]:\n"
                        output += self._dict_to_console(item, indent + 2)
                    else:
                        output += f"{indent_str}  - {item}\n"
            else:
                output += f"{indent_str}{key}: {value}\n"

        return output

    def _generate_technical_detail(self, execution_id: Optional[str]) -> dict[str, Any]:
        """
        Generate a technical detail report.

        Args:
            execution_id: Optional execution ID to report on

        Returns:
            Report data as a dictionary
        """
        # Get execution data
        execution = None
        if execution_id:
            execution = self.tracker.get_execution(execution_id)
        else:
            recent = self.tracker.get_recent_executions(1)
            if recent:
                execution = recent[0]
                execution_id = execution.get("execution_id", "unknown")

        if not execution:
            return {
                "title": "Technical Detail Report",
                "timestamp": datetime.datetime.now().isoformat(),
                "error": "No execution data found",
            }

        # Get validation results
        validation_results = self.validator.validate_execution(execution_id)

        # Extract stage details
        stages = execution.get("stages", {})
        stage_details = []

        for stage_name, stage_data in stages.items():
            stage_details.append(
                {
                    "name": stage_name,
                    "status": stage_data.get("status", "unknown"),
                    "start_time": stage_data.get("start_time", ""),
                    "end_time": stage_data.get("end_time", ""),
                    "duration": stage_data.get("duration", 0),
                    "retry_count": stage_data.get("retry_count", 0),
                    "error": stage_data.get("error", None),
                }
            )

        # Extract failure details
        failures = execution.get("failures", [])

        # Extract resolution attempts
        resolution_attempts = execution.get("resolution_attempts", [])

        # Generate report
        return {
            "title": "E2E Pipeline Technical Detail Report",
            "timestamp": datetime.datetime.now().isoformat(),
            "execution_id": execution_id,
            "execution_status": execution.get("status", "unknown"),
            "execution_start": execution.get("start_time", ""),
            "execution_end": execution.get("end_time", ""),
            "execution_duration": execution.get("duration", 0),
            "validation_results": validation_results,
            "stage_details": stage_details,
            "failures": failures,
            "resolution_attempts": resolution_attempts,
        }

    def _generate_trend_analysis(self, num_executions: int) -> dict[str, Any]:
        """
        Generate a trend analysis report.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Report data as a dictionary
        """
        # Get recent executions
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return {
                "title": "E2E Pipeline Trend Analysis",
                "timestamp": datetime.datetime.now().isoformat(),
                "error": "No execution data found",
            }

        # Calculate metrics
        success_rate = self.metrics.calculate_success_rate(num_executions)
        stage_success_rates = self.metrics.calculate_stage_success_rates(num_executions)
        avg_duration = self.metrics.calculate_average_duration(num_executions)
        stage_avg_durations = self.metrics.calculate_stage_average_durations(
            num_executions
        )
        failure_counts = self.metrics.calculate_failure_counts(num_executions)
        retry_rates = self.metrics.calculate_retry_rates(num_executions)

        # Analyze patterns
        history_analysis = self.analyzer.analyze_execution_history(num_executions)
        recurring_patterns = history_analysis.get("recurring_patterns", [])
        stage_reliability = history_analysis.get("stage_reliability", {})

        # Extract execution trend data
        execution_trend = []

        for execution in executions:
            execution_id = execution.get("execution_id", "unknown")
            status = execution.get("status", "unknown")
            start_time = execution.get("start_time", "")
            duration = execution.get("duration", 0)
            failure_count = len(execution.get("failures", []))

            execution_trend.append(
                {
                    "execution_id": execution_id,
                    "status": status,
                    "start_time": start_time,
                    "duration": duration,
                    "failure_count": failure_count,
                }
            )

        # Sort by start time
        execution_trend.sort(key=lambda x: x.get("start_time", ""))

        # Generate report
        return {
            "title": "E2E Pipeline Trend Analysis",
            "timestamp": datetime.datetime.now().isoformat(),
            "period": f"Last {len(executions)} executions",
            "overall_metrics": {
                "success_rate": success_rate,
                "average_duration": avg_duration,
                "trend": (
                    "Improving"
                    if success_rate > 80
                    else "Stable" if success_rate > 60 else "Declining"
                ),
            },
            "stage_metrics": {
                "success_rates": stage_success_rates,
                "average_durations": stage_avg_durations,
                "retry_rates": retry_rates,
                "reliability": stage_reliability,
            },
            "failure_analysis": {
                "failure_counts": failure_counts,
                "recurring_patterns": recurring_patterns,
            },
            "execution_trend": execution_trend,
        }

    def _generate_test_coverage_report(
        self, execution_id: Optional[str]
    ) -> dict[str, Any]:
        """
        Generate a test coverage report.

        Args:
            execution_id: Optional execution ID to report on

        Returns:
            Report data as a dictionary
        """
        # Get validation results
        validation_results = self.validator.validate_test_coverage(execution_id)

        # Get recent executions for trend
        self.tracker.get_recent_executions(10)

        # Calculate stage success rates
        stage_success_rates = self.metrics.calculate_stage_success_rates(10)

        # Generate report
        return {
            "title": "E2E Pipeline Test Coverage Report",
            "timestamp": datetime.datetime.now().isoformat(),
            "validation_results": validation_results,
            "stage_success_rates": stage_success_rates,
            "required_stages": self.validator.requirements.get("test_coverage", {}).get(
                "required_stages", []
            ),
            "critical_stages": self.validator.requirements.get("test_coverage", {}).get(
                "critical_stages", []
            ),
        }

    def _generate_issue_report(self, execution_id: Optional[str]) -> dict[str, Any]:
        """
        Generate an issue report.

        Args:
            execution_id: Optional execution ID to report on

        Returns:
            Report data as a dictionary
        """
        # Get execution data
        execution = None
        if execution_id:
            execution = self.tracker.get_execution(execution_id)
        else:
            recent = self.tracker.get_recent_executions(1)
            if recent:
                execution = recent[0]
                execution_id = execution.get("execution_id", "unknown")

        if not execution:
            return {
                "title": "E2E Pipeline Issue Report",
                "timestamp": datetime.datetime.now().isoformat(),
                "error": "No execution data found",
            }

        # Extract failures
        failures = execution.get("failures", [])

        if not failures:
            return {
                "title": "E2E Pipeline Issue Report",
                "timestamp": datetime.datetime.now().isoformat(),
                "execution_id": execution_id,
                "message": "No issues detected in this execution",
            }

        # Analyze failures
        analyzed_failures = []

        for failure in failures:
            stage = failure.get("stage", "unknown")
            message = failure.get("message", "")
            category = failure.get("category", "unknown")
            resolution = failure.get("resolution", "")

            # Analyze failure
            matching_patterns, context = self.analyzer.analyze_failure(stage, message)

            analyzed_failure = {
                "stage": stage,
                "message": message,
                "category": category,
                "resolution": resolution,
                "patterns": [],
            }

            if matching_patterns:
                for pattern in matching_patterns:
                    analyzed_failure["patterns"].append(
                        {
                            "pattern_id": pattern.pattern_id,
                            "name": pattern.name,
                            "description": pattern.description,
                            "auto_resolvable": pattern.auto_resolvable,
                            "resolution_steps": pattern.resolution_steps,
                        }
                    )

            analyzed_failures.append(analyzed_failure)

        # Extract resolution attempts
        resolution_attempts = execution.get("resolution_attempts", [])

        # Generate report
        return {
            "title": "E2E Pipeline Issue Report",
            "timestamp": datetime.datetime.now().isoformat(),
            "execution_id": execution_id,
            "execution_status": execution.get("status", "unknown"),
            "execution_time": execution.get("start_time", ""),
            "failure_count": len(failures),
            "failures": analyzed_failures,
            "resolution_attempts": resolution_attempts,
        }

    def _generate_performance_metrics(self, num_executions: int) -> dict[str, Any]:
        """
        Generate a performance metrics report.

        Args:
            num_executions: Number of recent executions to analyze

        Returns:
            Report data as a dictionary
        """
        # Get recent executions
        executions = self.tracker.get_recent_executions(num_executions)

        if not executions:
            return {
                "title": "E2E Pipeline Performance Metrics",
                "timestamp": datetime.datetime.now().isoformat(),
                "error": "No execution data found",
            }

        # Calculate average duration
        avg_duration = self.metrics.calculate_average_duration(num_executions)

        # Calculate stage average durations
        stage_avg_durations = self.metrics.calculate_stage_average_durations(
            num_executions
        )

        # Extract execution durations for trend
        execution_durations = []

        for execution in executions:
            execution_id = execution.get("execution_id", "unknown")
            status = execution.get("status", "unknown")
            start_time = execution.get("start_time", "")
            duration = execution.get("duration", 0)

            execution_durations.append(
                {
                    "execution_id": execution_id,
                    "status": status,
                    "start_time": start_time,
                    "duration": duration,
                }
            )

        # Sort by start time
        execution_durations.sort(key=lambda x: x.get("start_time", ""))

        # Get performance requirements
        max_duration = self.validator.requirements.get("performance", {}).get(
            "max_duration_seconds", {}
        )

        # Calculate performance status for each stage
        stage_performance = {}

        for stage, avg_duration in stage_avg_durations.items():
            max_stage_duration = max_duration.get(stage, 300)  # Default 5 min

            if avg_duration > max_stage_duration:
                status = "Critical"
            elif avg_duration > max_stage_duration * 0.8:
                status = "Warning"
            else:
                status = "Good"

            stage_performance[stage] = {
                "average_duration": avg_duration,
                "max_duration": max_stage_duration,
                "status": status,
                "utilization": (
                    (avg_duration / max_stage_duration) * 100
                    if max_stage_duration > 0
                    else 0.0
                ),
            }

        # Generate report
        return {
            "title": "E2E Pipeline Performance Metrics",
            "timestamp": datetime.datetime.now().isoformat(),
            "period": f"Last {len(executions)} executions",
            "overall_performance": {
                "average_duration": avg_duration,
                "status": (
                    "Good"
                    if avg_duration < max_duration.get("total", 900)
                    else "Warning"
                ),
            },
            "stage_performance": stage_performance,
            "execution_durations": execution_durations,
        }

    def _generate_daily_summary(self) -> dict[str, Any]:
        """
        Generate a daily summary report.

        Returns:
            Report data as a dictionary
        """
        # Get today's date
        today = datetime.datetime.now().date()

        # Get all executions
        all_executions = self.tracker.get_recent_executions(100)

        # Filter for today's executions
        today_executions = []

        for execution in all_executions:
            start_time = execution.get("start_time", "")

            if start_time:
                try:
                    execution_date = datetime.datetime.fromisoformat(start_time).date()
                    if execution_date == today:
                        today_executions.append(execution)
                except (ValueError, TypeError):
                    # Skip executions with invalid timestamps
                    pass

        if not today_executions:
            return {
                "title": "E2E Pipeline Daily Summary",
                "date": today.isoformat(),
                "timestamp": datetime.datetime.now().isoformat(),
                "message": "No executions found for today",
            }

        # Calculate metrics
        success_count = sum(1 for e in today_executions if e.get("status") == "success")
        failure_count = len(today_executions) - success_count
        success_rate = (
            (success_count / len(today_executions)) * 100 if today_executions else 0.0
        )

        # Count failures by category
        failure_categories = defaultdict(int)

        for execution in today_executions:
            for failure in execution.get("failures", []):
                category = failure.get("category", "unknown")
                failure_categories[category] += 1

        # Generate report
        return {
            "title": "E2E Pipeline Daily Summary",
            "date": today.isoformat(),
            "timestamp": datetime.datetime.now().isoformat(),
            "execution_count": len(today_executions),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_rate,
            "failure_categories": dict(failure_categories),
            "executions": [
                {
                    "execution_id": e.get("execution_id", "unknown"),
                    "status": e.get("status", "unknown"),
                    "start_time": e.get("start_time", ""),
                    "duration": e.get("duration", 0),
                    "failure_count": len(e.get("failures", [])),
                }
                for e in today_executions
            ],
        }

    def _generate_weekly_summary(self) -> dict[str, Any]:
        """
        Generate a weekly summary report.

        Returns:
            Report data as a dictionary
        """
        # Get the date range for this week (last 7 days)
        today = datetime.datetime.now().date()
        week_start = today - datetime.timedelta(days=6)  # 7 days including today

        # Get all executions
        all_executions = self.tracker.get_recent_executions(100)

        # Filter for this week's executions
        week_executions = []

        for execution in all_executions:
            start_time = execution.get("start_time", "")

            if start_time:
                try:
                    execution_date = datetime.datetime.fromisoformat(start_time).date()
                    if week_start <= execution_date <= today:
                        week_executions.append(execution)
                except (ValueError, TypeError):
                    # Skip executions with invalid timestamps
                    pass

        if not week_executions:
            return {
                "title": "E2E Pipeline Weekly Summary",
                "period": f"{week_start.isoformat()} to {today.isoformat()}",
                "timestamp": datetime.datetime.now().isoformat(),
                "message": "No executions found for this week",
            }

        # Calculate overall metrics
        success_count = sum(1 for e in week_executions if e.get("status") == "success")
        failure_count = len(week_executions) - success_count
        success_rate = (
            (success_count / len(week_executions)) * 100 if week_executions else 0.0
        )

        # Group executions by day
        daily_metrics = {}

        for day_offset in range(7):
            date = today - datetime.timedelta(days=day_offset)
            date_str = date.isoformat()

            # Filter executions for this day
            day_executions = []

            for execution in week_executions:
                start_time = execution.get("start_time", "")

                if start_time:
                    try:
                        execution_date = datetime.datetime.fromisoformat(
                            start_time
                        ).date()
                        if execution_date == date:
                            day_executions.append(execution)
                    except (ValueError, TypeError):
                        # Skip executions with invalid timestamps
                        pass

            # Calculate daily metrics
            day_success_count = sum(
                1 for e in day_executions if e.get("status") == "success"
            )
            day_failure_count = len(day_executions) - day_success_count
            day_success_rate = (
                (day_success_count / len(day_executions)) * 100
                if day_executions
                else 0.0
            )

            daily_metrics[date_str] = {
                "execution_count": len(day_executions),
                "success_count": day_success_count,
                "failure_count": day_failure_count,
                "success_rate": day_success_rate,
            }

        # Count failures by category
        failure_categories = defaultdict(int)

        for execution in week_executions:
            for failure in execution.get("failures", []):
                category = failure.get("category", "unknown")
                failure_categories[category] += 1

        # Generate report
        return {
            "title": "E2E Pipeline Weekly Summary",
            "period": f"{week_start.isoformat()} to {today.isoformat()}",
            "timestamp": datetime.datetime.now().isoformat(),
            "overall_metrics": {
                "execution_count": len(week_executions),
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate,
            },
            "daily_metrics": daily_metrics,
            "failure_categories": dict(failure_categories),
        }

    def distribute_report(
        self,
        report_path: str,
        distribution_channel: str,
        recipients: Optional[list[str]] = None,
    ) -> bool:
        """
        Distribute a report through the specified channel.

        Args:
            report_path: Path to the report file
            distribution_channel: Channel to distribute through (email, slack, etc.)
            recipients: List of recipients (email addresses, Slack channels, etc.)

        Returns:
            True if the report was successfully distributed, False otherwise
        """
        if distribution_channel == "email":
            return self._distribute_via_email(report_path, recipients)
        elif distribution_channel == "slack":
            return self._distribute_via_slack(report_path, recipients)
        else:
            logger.error(f"Unsupported distribution channel: {distribution_channel}")
            return False

    def _distribute_via_email(
        self, report_path: str, recipients: Optional[list[str]]
    ) -> bool:
        """
        Distribute a report via email.

        Args:
            report_path: Path to the report file
            recipients: List of email recipients

        Returns:
            True if the report was successfully distributed, False otherwise
        """
        # Check if recipients are provided
        if not recipients:
            logger.error("No email recipients specified")
            return False

        # Check if the report file exists
        if not os.path.exists(report_path):
            logger.error(f"Report file not found: {report_path}")
            return False

        # Get the report format from the file extension
        _, ext = os.path.splitext(report_path)

        # Read the report content
        with open(report_path) as f:
            f.read()

        # TODO: Implement actual email sending logic here
        # This would typically involve SMTP or a service like SendGrid

        logger.info(f"Would send email to {recipients} with report {report_path}")
        return True

    def _distribute_via_slack(
        self, report_path: str, channels: Optional[list[str]]
    ) -> bool:
        """
        Distribute a report via Slack.

        Args:
            report_path: Path to the report file
            channels: List of Slack channels

        Returns:
            True if the report was successfully distributed, False otherwise
        """
        # Check if channels are provided
        if not channels:
            logger.error("No Slack channels specified")
            return False

        # Check if the report file exists
        if not os.path.exists(report_path):
            logger.error(f"Report file not found: {report_path}")
            return False

        # TODO: Implement actual Slack sending logic here
        # This would typically involve the Slack API

        logger.info(f"Would send report {report_path} to Slack channels {channels}")
        return True


def main():
    """
    Main entry point for the report generator.
    """
    import argparse

    parser = argparse.ArgumentParser(description="E2E Pipeline Report Generator")
    parser.add_argument(
        "--type", "-t", required=True, help="Type of report to generate"
    )
    parser.add_argument("--format", "-f", default="html", help="Output format")
    parser.add_argument("--execution-id", "-e", help="Execution ID to report on")
    parser.add_argument(
        "--num-executions",
        "-n",
        type=int,
        default=10,
        help="Number of executions to analyze",
    )
    parser.add_argument("--output-dir", "-o", help="Output directory for reports")
    parser.add_argument(
        "--distribute", "-d", action="store_true", help="Distribute the report"
    )
    parser.add_argument("--channel", "-c", help="Distribution channel (email, slack)")
    parser.add_argument("--recipients", "-r", help="Comma-separated list of recipients")

    args = parser.parse_args()

    # Check if the report type is valid
    valid_types = [t for t in dir(ReportType) if not t.startswith("__")]
    if args.type.upper() not in valid_types:
        return 1

    # Check if the output format is valid
    valid_formats = [f for f in dir(OutputFormat) if not f.startswith("__")]
    if args.format.upper() not in valid_formats:
        return 1

    # Generate the report
    report_type = getattr(ReportType, args.type.upper())
    output_format = getattr(OutputFormat, args.format.upper())

    generator = ReportGenerator(output_dir=args.output_dir)

    try:
        report_path = generator.generate_report(
            report_type=report_type,
            output_format=output_format,
            execution_id=args.execution_id,
            num_executions=args.num_executions,
        )

        # Distribute the report if requested
        if args.distribute and args.channel and args.recipients:
            recipients = args.recipients.split(",")

            success = generator.distribute_report(
                report_path=report_path,
                distribution_channel=args.channel,
                recipients=recipients,
            )

            if success:
                pass
            else:
                return 1

        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
