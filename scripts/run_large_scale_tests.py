#!/usr/bin/env python3
"""
Script to run large-scale validation tests for the LeadFactory pipeline.

This script executes the large-scale validation tests and generates
performance reports based on the results.
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add parent directory to path so we can import from leadfactory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("large_scale_tests")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run large-scale validation tests for the LeadFactory pipeline."
    )
    parser.add_argument(
        "--lead-count",
        type=int,
        default=10000,
        help="Number of leads to test (default: 10000)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="performance_reports",
        help="Directory to store performance reports (default: performance_reports)",
    )
    parser.add_argument(
        "--generate-charts",
        action="store_true",
        help="Generate performance charts",
    )
    parser.add_argument(
        "--test-failures",
        action="store_true",
        help="Run tests that simulate failure scenarios",
    )
    parser.add_argument(
        "--test-bottlenecks",
        action="store_true",
        help="Run tests that identify performance bottlenecks",
    )
    parser.add_argument(
        "--skip-10k",
        action="store_true",
        help="Skip the 10,000 lead test (useful for quick testing)",
    )
    parser.add_argument(
        "--verify-thresholds",
        action="store_true",
        help="Verify performance against required thresholds",
    )
    parser.add_argument(
        "--min-throughput",
        type=float,
        default=100.0,
        help="Minimum acceptable throughput in leads per minute (default: 100)",
    )
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=0.01,
        help="Maximum acceptable error rate (default: 0.01 = 1%)",
    )
    parser.add_argument(
        "--max-runtime-minutes",
        type=float,
        default=180.0,
        help="Maximum acceptable runtime in minutes (default: 180)",
    )

    return parser.parse_args()


def run_pytest_command(test_name, output_file=None, junit_file=None, extra_args=None):
    """Run a pytest command and capture the output."""
    command = ["pytest", "-xvs", test_name]

    if output_file:
        command.extend(["-o", "console_output_style=classic", "--no-header"])

    if junit_file:
        command.extend(["--junitxml", junit_file])

    if extra_args:
        command.extend(extra_args)

    logger.info(f"Running command: {' '.join(command)}")

    if output_file:
        with open(output_file, "w") as f:
            process = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT)
            process.wait()
    else:
        process = subprocess.run(command)

    return process.returncode


def extract_metrics_from_output(output_file):
    """Extract performance metrics from test output."""
    metrics = {}

    try:
        with open(output_file) as f:
            content = f.read()

            # Look for JSON metrics in the output
            json_start = content.find('{"total_time_seconds":')
            if json_start >= 0:
                json_end = content.find("}", json_start)
                while content.find("}", json_end + 1) > 0:
                    json_end = content.find("}", json_end + 1)
                json_end += 1

                metrics_str = content[json_start:json_end]
                try:
                    metrics = json.loads(metrics_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse metrics JSON: {e}")
                    logger.error(f"JSON string: {metrics_str}")
    except Exception as e:
        logger.error(f"Error extracting metrics: {e}")

    return metrics


def generate_performance_report(metrics_dict, output_dir, lead_count):
    """Generate a performance report from test metrics."""
    report_path = Path(output_dir) / "performance_summary.md"

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Save raw metrics
    metrics_file = Path(output_dir) / "raw_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics_dict, f, indent=2)

    # Create report
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        "# LeadFactory Large-Scale Validation Report",
        "",
        f"**Generated:** {timestamp}",
        f"**Lead Count:** {lead_count}",
        "",
        "## Overall Performance",
        "",
    ]

    # Add overall metrics if available
    if "total_time_seconds" in metrics_dict:
        total_time = metrics_dict["total_time_seconds"]
        minutes = int(total_time // 60)
        seconds = int(total_time % 60)

        throughput_per_minute = metrics_dict.get("throughput_per_minute", 0)
        success_rate = metrics_dict.get("success_rate", 0) * 100

        report_lines.extend(
            [
                f"- **Total Processing Time:** {minutes} minutes {seconds} seconds",
                f"- **Throughput:** {throughput_per_minute:.2f} leads/minute",
                f"- **Success Rate:** {success_rate:.2f}%",
                f"- **Total Processed:** {metrics_dict.get('total_processed', 0)}",
                f"- **Total Succeeded:** {metrics_dict.get('total_succeeded', 0)}",
                "",
            ]
        )

    # Add stage metrics if available
    if "stage_metrics" in metrics_dict:
        report_lines.append("## Stage Performance\n")

        for stage, stage_metrics in metrics_dict["stage_metrics"].items():
            avg_time = stage_metrics.get("avg_time_seconds", 0) * 1000  # Convert to ms
            failure_rate = stage_metrics.get("failure_rate", 0) * 100

            report_lines.extend(
                [
                    f"### {stage.capitalize()} Stage",
                    "",
                    f"- **Average Processing Time:** {avg_time:.2f} ms",
                    f"- **Failure Rate:** {failure_rate:.2f}%",
                    f"- **Failures:** {stage_metrics.get('failure_count', 0)}",
                    "",
                ]
            )

    # Add recommendations based on metrics
    report_lines.append("## Recommendations\n")

    if "stage_metrics" in metrics_dict:
        # Find slowest stage
        slowest_stage = max(
            metrics_dict["stage_metrics"].items(),
            key=lambda x: x[1].get("avg_time_seconds", 0),
        )
        slowest_stage_name = slowest_stage[0]
        slowest_stage_time = (
            slowest_stage[1].get("avg_time_seconds", 0) * 1000
        )  # Convert to ms

        report_lines.append(
            f"- **Performance Bottleneck:** The {slowest_stage_name} stage is the slowest at {slowest_stage_time:.2f} ms per lead."
        )

    if "throughput_per_minute" in metrics_dict:
        throughput = metrics_dict["throughput_per_minute"]
        if throughput < 100:
            report_lines.append(
                f"- **Throughput Concern:** Current throughput ({throughput:.2f} leads/min) is below the target of 100 leads/min."
            )

    if "success_rate" in metrics_dict:
        success_rate = metrics_dict["success_rate"]
        if success_rate < 0.99:
            report_lines.append(
                f"- **Reliability Concern:** Success rate ({success_rate:.2%}) is below the target of 99%."
            )

    # Write report to file
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))

    logger.info(f"Performance report written to {report_path}")

    return report_path


def verify_performance_thresholds(metrics, args):
    """Verify that performance meets the required thresholds."""
    problems = []

    # Check throughput
    if "throughput_per_minute" in metrics:
        throughput = metrics["throughput_per_minute"]
        if throughput < args.min_throughput:
            problems.append(
                f"Throughput ({throughput:.2f} leads/min) is below minimum threshold ({args.min_throughput} leads/min)"
            )

    # Check error rate
    if "success_rate" in metrics:
        error_rate = 1.0 - metrics["success_rate"]
        if error_rate > args.max_error_rate:
            problems.append(
                f"Error rate ({error_rate:.2%}) exceeds maximum threshold ({args.max_error_rate:.2%})"
            )

    # Check runtime
    if "total_time_seconds" in metrics:
        runtime_minutes = metrics["total_time_seconds"] / 60.0
        if runtime_minutes > args.max_runtime_minutes:
            problems.append(
                f"Runtime ({runtime_minutes:.2f} minutes) exceeds maximum threshold ({args.max_runtime_minutes} minutes)"
            )

    # Check stage error rates
    if "stage_metrics" in metrics:
        for stage, stage_metrics in metrics["stage_metrics"].items():
            if (
                "failure_rate" in stage_metrics
                and stage_metrics["failure_rate"] > args.max_error_rate
            ):
                problems.append(
                    f"{stage.capitalize()} stage failure rate ({stage_metrics['failure_rate']:.2%}) exceeds maximum threshold ({args.max_error_rate:.2%})"
                )

    # Display results
    if problems:
        logger.error("Performance verification failed:")
        for problem in problems:
            logger.error(f"- {problem}")
        return False
    else:
        logger.info("Performance verification passed! All thresholds met.")
        return True


def main():
    """Main function."""
    args = parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Keep track of test results
    all_tests_passed = True
    metrics_collection = {}

    # Run 100-lead test
    logger.info("Running 100-lead validation test...")
    test_output = os.path.join(args.output_dir, "test_100_leads_output.txt")
    junit_output = os.path.join(args.output_dir, "test_100_leads_junit.xml")

    result_100 = run_pytest_command(
        "tests/integration/test_large_scale_validation.py::test_large_scale_100_leads",
        test_output,
        junit_output,
    )

    if result_100 == 0:
        logger.info("100-lead test passed!")
        metrics_100 = extract_metrics_from_output(test_output)
        metrics_collection["100_leads"] = metrics_100
    else:
        logger.error("100-lead test failed!")
        all_tests_passed = False

    # Run 1000-lead test
    logger.info("Running 1000-lead validation test...")
    test_output = os.path.join(args.output_dir, "test_1000_leads_output.txt")
    junit_output = os.path.join(args.output_dir, "test_1000_leads_junit.xml")

    result_1000 = run_pytest_command(
        "tests/integration/test_large_scale_validation.py::test_large_scale_1000_leads",
        test_output,
        junit_output,
    )

    if result_1000 == 0:
        logger.info("1000-lead test passed!")
        metrics_1000 = extract_metrics_from_output(test_output)
        metrics_collection["1000_leads"] = metrics_1000
    else:
        logger.error("1000-lead test failed!")
        all_tests_passed = False

    # Run 10000-lead test (unless skipped)
    if not args.skip_10k:
        logger.info("Running 10000-lead validation test (this may take a while)...")
        test_output = os.path.join(args.output_dir, "test_10000_leads_output.txt")
        junit_output = os.path.join(args.output_dir, "test_10000_leads_junit.xml")

        result_10000 = run_pytest_command(
            "tests/integration/test_large_scale_validation.py::test_large_scale_10000_leads",
            test_output,
            junit_output,
        )

        if result_10000 == 0:
            logger.info("10000-lead test passed!")
            metrics_10000 = extract_metrics_from_output(test_output)
            metrics_collection["10000_leads"] = metrics_10000

            # This is the primary metrics we care about for verification
            if args.verify_thresholds:
                verification_passed = verify_performance_thresholds(metrics_10000, args)
                if not verification_passed:
                    all_tests_passed = False
        else:
            logger.error("10000-lead test failed!")
            all_tests_passed = False

    # Run failure scenario tests if requested
    if args.test_failures:
        logger.info("Running failure scenario tests...")
        test_output = os.path.join(args.output_dir, "test_failure_scenarios_output.txt")
        junit_output = os.path.join(args.output_dir, "test_failure_scenarios_junit.xml")

        result_failures = run_pytest_command(
            "tests/integration/test_large_scale_validation.py::test_large_scale_failure_scenarios",
            test_output,
            junit_output,
        )

        if result_failures == 0:
            logger.info("Failure scenario tests passed!")
            metrics_failures = extract_metrics_from_output(test_output)
            metrics_collection["failure_scenarios"] = metrics_failures
        else:
            logger.error("Failure scenario tests failed!")
            # Don't fail the overall run for this test

    # Run bottleneck tests if requested
    if args.test_bottlenecks:
        logger.info("Running performance bottleneck tests...")
        test_output = os.path.join(args.output_dir, "test_bottlenecks_output.txt")
        junit_output = os.path.join(args.output_dir, "test_bottlenecks_junit.xml")

        result_bottlenecks = run_pytest_command(
            "tests/integration/test_large_scale_validation.py::test_large_scale_performance_bottlenecks",
            test_output,
            junit_output,
        )

        if result_bottlenecks == 0:
            logger.info("Performance bottleneck tests passed!")
            metrics_bottlenecks = extract_metrics_from_output(test_output)
            metrics_collection["bottlenecks"] = metrics_bottlenecks
        else:
            logger.error("Performance bottleneck tests failed!")
            # Don't fail the overall run for this test

    # Save all metrics
    metrics_file = os.path.join(args.output_dir, "all_metrics.json")
    with open(metrics_file, "w") as f:
        json.dump(metrics_collection, f, indent=2)

    # Generate performance report
    if not args.skip_10k and "10000_leads" in metrics_collection:
        primary_metrics = metrics_collection["10000_leads"]
        report_path = generate_performance_report(
            primary_metrics, args.output_dir, args.lead_count
        )
        logger.info(f"Generated performance report: {report_path}")

    # Generate charts if requested
    if args.generate_charts and "matplotlib" in sys.modules:
        try:
            import matplotlib.pyplot as plt

            # Create charts directory
            charts_dir = os.path.join(args.output_dir, "charts")
            os.makedirs(charts_dir, exist_ok=True)

            # Generate comparison charts if we have multiple test results
            if len(metrics_collection) > 1:
                # Throughput comparison
                plt.figure(figsize=(10, 6))
                labels = []
                throughputs = []

                for test_name, metrics in metrics_collection.items():
                    if "throughput_per_minute" in metrics:
                        labels.append(test_name)
                        throughputs.append(metrics["throughput_per_minute"])

                if throughputs:
                    plt.bar(labels, throughputs)
                    plt.title("Throughput Comparison")
                    plt.ylabel("Leads per Minute")
                    plt.grid(True, linestyle="--", alpha=0.7)
                    plt.savefig(
                        os.path.join(charts_dir, "throughput_comparison.png"), dpi=300
                    )
                    plt.close()

                # Success rate comparison
                plt.figure(figsize=(10, 6))
                labels = []
                success_rates = []

                for test_name, metrics in metrics_collection.items():
                    if "success_rate" in metrics:
                        labels.append(test_name)
                        success_rates.append(
                            metrics["success_rate"] * 100
                        )  # Convert to percentage

                if success_rates:
                    plt.bar(labels, success_rates)
                    plt.title("Success Rate Comparison")
                    plt.ylabel("Success Rate (%)")
                    plt.ylim(min(min(success_rates) - 5, 90), 100)
                    plt.grid(True, linestyle="--", alpha=0.7)
                    plt.savefig(
                        os.path.join(charts_dir, "success_rate_comparison.png"), dpi=300
                    )
                    plt.close()

            logger.info(f"Generated performance charts in {charts_dir}")
        except Exception as e:
            logger.error(f"Failed to generate charts: {e}")

    # Return appropriate exit code
    if all_tests_passed:
        logger.info("All large-scale validation tests passed!")
        return 0
    else:
        logger.error("Some large-scale validation tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
