#!/usr/bin/env python3
"""
Script to verify success criteria for large-scale validation.
"""

import argparse
import glob
import json
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("validation_verify")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify success criteria for large-scale validation."
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        required=True,
        help="Directory containing performance metrics JSON files",
    )
    parser.add_argument(
        "--lead-count",
        type=int,
        default=10000,
        help="Number of leads processed in the validation (default: 10000)",
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


def find_latest_metrics_file(metrics_dir):
    """Find the most recent metrics JSON file in the input directory."""
    metrics_path = Path(metrics_dir)

    if not metrics_path.exists() or not metrics_path.is_dir():
        raise ValueError(f"Metrics directory does not exist: {metrics_dir}")

    metrics_files = list(metrics_path.glob("validation_metrics_*.json"))
    if not metrics_files:
        raise ValueError(f"No metrics files found in: {metrics_dir}")

    return max(metrics_files, key=lambda p: p.stat().st_mtime)


def load_metrics(metrics_file):
    """Load metrics from a JSON file."""
    with open(metrics_file, "r") as f:
        return json.load(f)


def verify_success_criteria(metrics, args):
    """Verify if the validation results meet the success criteria."""
    overall = metrics["overall"]
    success_criteria = []

    # Check throughput (convert from per second to per minute)
    throughput_per_minute = overall["throughput"] * 60
    if throughput_per_minute >= args.min_throughput:
        success_criteria.append(
            {
                "name": "Throughput",
                "success": True,
                "value": f"{throughput_per_minute:.2f} leads/minute",
                "threshold": f">= {args.min_throughput} leads/minute",
            }
        )
    else:
        success_criteria.append(
            {
                "name": "Throughput",
                "success": False,
                "value": f"{throughput_per_minute:.2f} leads/minute",
                "threshold": f">= {args.min_throughput} leads/minute",
                "message": f"Throughput is below the minimum threshold. Current: {throughput_per_minute:.2f} leads/minute, Required: {args.min_throughput} leads/minute",
            }
        )

    # Check error rate
    error_rate = 1.0 - overall["success_rate"]
    if error_rate <= args.max_error_rate:
        success_criteria.append(
            {
                "name": "Error Rate",
                "success": True,
                "value": f"{error_rate:.2%}",
                "threshold": f"<= {args.max_error_rate:.2%}",
            }
        )
    else:
        success_criteria.append(
            {
                "name": "Error Rate",
                "success": False,
                "value": f"{error_rate:.2%}",
                "threshold": f"<= {args.max_error_rate:.2%}",
                "message": f"Error rate is above the maximum threshold. Current: {error_rate:.2%}, Maximum allowed: {args.max_error_rate:.2%}",
            }
        )

    # Check runtime
    runtime_minutes = overall["time"] / 60.0
    if runtime_minutes <= args.max_runtime_minutes:
        success_criteria.append(
            {
                "name": "Runtime",
                "success": True,
                "value": f"{runtime_minutes:.2f} minutes",
                "threshold": f"<= {args.max_runtime_minutes} minutes",
            }
        )
    else:
        success_criteria.append(
            {
                "name": "Runtime",
                "success": False,
                "value": f"{runtime_minutes:.2f} minutes",
                "threshold": f"<= {args.max_runtime_minutes} minutes",
                "message": f"Runtime is above the maximum threshold. Current: {runtime_minutes:.2f} minutes, Maximum allowed: {args.max_runtime_minutes} minutes",
            }
        )

    # Check lead count
    if metrics.get("lead_count", 0) >= args.lead_count:
        success_criteria.append(
            {
                "name": "Lead Count",
                "success": True,
                "value": f"{metrics.get('lead_count', 0)}",
                "threshold": f">= {args.lead_count}",
            }
        )
    else:
        success_criteria.append(
            {
                "name": "Lead Count",
                "success": False,
                "value": f"{metrics.get('lead_count', 0)}",
                "threshold": f">= {args.lead_count}",
                "message": f"Lead count is below the required amount. Current: {metrics.get('lead_count', 0)}, Required: {args.lead_count}",
            }
        )

    # Check for failures in specific stages
    stage_failures = []
    for stage, stage_metrics in metrics["stage_metrics"].items():
        if stage_metrics.get("failure_rate", 0) > args.max_error_rate:
            stage_failures.append(
                {
                    "stage": stage,
                    "failure_rate": stage_metrics["failure_rate"],
                    "message": f"Stage '{stage}' has a high failure rate of {stage_metrics['failure_rate']:.2%}, which exceeds the maximum allowed {args.max_error_rate:.2%}",
                }
            )

    if not stage_failures:
        success_criteria.append(
            {
                "name": "Stage Error Rates",
                "success": True,
                "value": "All stages within limits",
                "threshold": f"All <= {args.max_error_rate:.2%}",
            }
        )
    else:
        success_criteria.append(
            {
                "name": "Stage Error Rates",
                "success": False,
                "value": f"{len(stage_failures)} stages exceed limits",
                "threshold": f"All <= {args.max_error_rate:.2%}",
                "message": "\n".join(
                    [failure["message"] for failure in stage_failures]
                ),
            }
        )

    return success_criteria


def display_results(success_criteria):
    """Display the verification results."""
    print("\n=== Validation Success Criteria ===\n")

    all_passed = True
    for criteria in success_criteria:
        status = "✅ PASS" if criteria["success"] else "❌ FAIL"
        print(
            f"{status} | {criteria['name']}: {criteria['value']} (Threshold: {criteria['threshold']})"
        )

        if not criteria["success"]:
            all_passed = False
            print(f"       Error: {criteria.get('message', 'Failed to meet criteria')}")

    print("\n=== Summary ===\n")
    if all_passed:
        print("✅ ALL CRITERIA PASSED: The validation meets all success criteria.")
    else:
        print("❌ VALIDATION FAILED: One or more success criteria were not met.")

    print("")
    return all_passed


def main():
    """Main function."""
    args = parse_args()

    try:
        metrics_file = find_latest_metrics_file(args.metrics_dir)
        logger.info(f"Using metrics file: {metrics_file}")

        metrics = load_metrics(metrics_file)
        success_criteria = verify_success_criteria(metrics, args)

        all_passed = display_results(success_criteria)

        if not all_passed:
            logger.error("Validation failed to meet success criteria.")
            sys.exit(1)

        logger.info("Validation successfully met all criteria.")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error verifying validation: {str(e)}")
        sys.exit(2)


if __name__ == "__main__":
    main()
