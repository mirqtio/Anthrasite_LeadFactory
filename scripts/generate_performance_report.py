#!/usr/bin/env python3
"""
Script to generate performance reports from large-scale validation metrics.
"""

import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("performance_report")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate performance reports from validation metrics."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Directory containing performance metrics JSON files",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        required=True,
        help="Output file for the performance report (markdown format)",
    )
    parser.add_argument(
        "--lead-count",
        type=int,
        default=10000,
        help="Number of leads processed in the validation (default: 10000)",
    )

    return parser.parse_args()


def find_latest_metrics_file(input_dir):
    """Find the most recent metrics JSON file in the input directory."""
    input_path = Path(input_dir)

    if not input_path.exists() or not input_path.is_dir():
        raise ValueError(f"Input directory does not exist: {input_dir}")

    metrics_files = list(input_path.glob("validation_metrics_*.json"))
    if not metrics_files:
        raise ValueError(f"No metrics files found in: {input_dir}")

    return max(metrics_files, key=lambda p: p.stat().st_mtime)


def load_metrics(metrics_file):
    """Load metrics from a JSON file."""
    with open(metrics_file) as f:
        return json.load(f)


def generate_report(metrics, lead_count, output_file):
    """Generate a performance report in markdown format."""
    logger.info(f"Generating performance report for {lead_count} leads")

    # Extract key metrics
    overall = metrics["overall"]
    stage_metrics = metrics["stage_metrics"]
    batches = metrics["batches"]

    # Calculate additional metrics
    batch_throughputs = [batch["throughput"] for batch in batches]
    max_throughput = max(batch_throughputs) if batch_throughputs else 0
    min_throughput = min(batch_throughputs) if batch_throughputs else 0
    avg_throughput = (
        sum(batch_throughputs) / len(batch_throughputs) if batch_throughputs else 0
    )

    # Format timestamps
    try:
        start_time = datetime.datetime.fromisoformat(metrics["start_time"])
        end_time = datetime.datetime.fromisoformat(metrics["end_time"])
        duration = end_time - start_time
    except (ValueError, KeyError):
        start_time = "Unknown"
        end_time = "Unknown"
        duration = datetime.timedelta(seconds=overall["time"])

    # Create report
    report = [
        "# LeadFactory Performance Report",
        "",
        f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Lead Count:** {lead_count}",
        f"**Batch Size:** {metrics.get('batch_size', 'N/A')}",
        f"**Total Batches:** {len(batches)}",
        "",
        "## Overall Performance",
        "",
        f"- **Start Time:** {start_time}",
        f"- **End Time:** {end_time}",
        f"- **Total Duration:** {duration}",
        f"- **Overall Throughput:** {overall['throughput']:.2f} leads/second",
        f"- **Success Rate:** {overall['success_rate'] * 100:.2f}%",
        "",
        "## Stage Performance",
        "",
    ]

    # Add stage metrics
    for stage, metrics in stage_metrics.items():
        if "avg_time" in metrics:
            report.extend(
                [
                    f"### {stage.capitalize()} Stage",
                    "",
                    f"- **Average Processing Time:** {metrics['avg_time']:.4f} seconds per lead",
                    f"- **Total Processing Time:** {metrics['time']:.2f} seconds",
                    f"- **Leads Processed:** {metrics['count']}",
                    f"- **Failures:** {metrics['failures']} ({metrics.get('failure_rate', 0) * 100:.2f}%)",
                    "",
                ]
            )

    # Add batch performance
    report.extend(
        [
            "## Batch Performance",
            "",
            f"- **Maximum Throughput:** {max_throughput:.2f} leads/second",
            f"- **Minimum Throughput:** {min_throughput:.2f} leads/second",
            f"- **Average Throughput:** {avg_throughput:.2f} leads/second",
            "",
            "### Batch Details",
            "",
            "| Batch # | Lead Count | Processing Time (s) | Throughput (leads/s) | Success Rate (%) |",
            "|---------|------------|---------------------|----------------------|------------------|",
        ]
    )

    for batch in batches:
        success_rate = (
            (batch["success_count"] / batch["lead_count"]) * 100
            if batch["lead_count"] > 0
            else 0
        )
        report.append(
            f"| {batch['batch_num']} | {batch['lead_count']} | {batch['processing_time']:.2f} | "
            f"{batch['throughput']:.2f} | {success_rate:.2f} |"
        )

    # Add recommendations and conclusions
    report.extend(
        [
            "",
            "## Recommendations",
            "",
        ]
    )

    # Make recommendations based on metrics
    if overall["throughput"] < 10:
        report.append(
            "- **⚠️ Low Throughput:** Overall throughput is below target. Consider optimizing pipeline stages."
        )

    if overall["success_rate"] < 0.99:
        report.append(
            "- **⚠️ High Failure Rate:** Success rate is below 99%. Review error logs to identify and fix common failures."
        )

    # Look for bottlenecks
    if stage_metrics:
        slowest_stage = max(
            stage_metrics.items(), key=lambda x: x[1].get("avg_time", 0)
        )
        report.append(
            f"- **Bottleneck Identified:** The {slowest_stage[0]} stage is the slowest, with an average time of {slowest_stage[1].get('avg_time', 0):.4f} seconds per lead."
        )

    # Add conclusion
    report.extend(
        [
            "",
            "## Conclusion",
            "",
        ]
    )

    if overall["success_rate"] >= 0.99 and overall["throughput"] >= 10:
        report.append(
            "✅ **Pipeline Performance is Satisfactory:** The pipeline is processing leads efficiently with a high success rate."
        )
    else:
        report.append(
            "⚠️ **Pipeline Needs Optimization:** Performance issues were identified that require attention."
        )

    # Write report to file
    with open(output_file, "w") as f:
        f.write("\n".join(report))

    logger.info(f"Performance report written to {output_file}")


if __name__ == "__main__":
    args = parse_args()

    try:
        metrics_file = find_latest_metrics_file(args.input_dir)
        metrics = load_metrics(metrics_file)
        generate_report(metrics, args.lead_count, args.output_file)
        logger.info("Report generation completed successfully")
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        sys.exit(1)

    sys.exit(0)
