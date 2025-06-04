#!/usr/bin/env python3
"""
Script to generate performance charts from large-scale validation metrics.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    sys.stderr.write(
        "Error: This script requires matplotlib and numpy. Install with: pip install matplotlib numpy\n"
    )
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("performance_charts")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate performance charts from validation metrics."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Directory containing performance metrics JSON files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory for chart images",
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


def generate_throughput_chart(metrics, output_dir):
    """Generate a chart showing throughput by batch."""
    batch_nums = [batch["batch_num"] for batch in metrics["batches"]]
    throughputs = [batch["throughput"] for batch in metrics["batches"]]

    plt.figure(figsize=(10, 6))
    plt.plot(batch_nums, throughputs, marker="o", linestyle="-", color="blue")

    # Add horizontal line for average throughput
    avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0
    plt.axhline(
        y=avg_throughput,
        color="r",
        linestyle="--",
        label=f"Avg: {avg_throughput:.2f} leads/s",
    )

    plt.title("Throughput by Batch")
    plt.xlabel("Batch Number")
    plt.ylabel("Throughput (leads/second)")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend()

    # Save chart
    output_path = Path(output_dir) / "throughput_by_batch.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Generated throughput chart: {output_path}")


def generate_success_rate_chart(metrics, output_dir):
    """Generate a chart showing success rate by batch."""
    batch_nums = [batch["batch_num"] for batch in metrics["batches"]]
    success_rates = [
        (
            (batch["success_count"] / batch["lead_count"]) * 100
            if batch["lead_count"] > 0
            else 0
        )
        for batch in metrics["batches"]
    ]

    plt.figure(figsize=(10, 6))
    plt.plot(batch_nums, success_rates, marker="o", linestyle="-", color="green")

    # Add horizontal line for overall success rate
    overall_success_rate = metrics["overall"]["success_rate"] * 100
    plt.axhline(
        y=overall_success_rate,
        color="r",
        linestyle="--",
        label=f"Overall: {overall_success_rate:.2f}%",
    )

    plt.title("Success Rate by Batch")
    plt.xlabel("Batch Number")
    plt.ylabel("Success Rate (%)")
    plt.ylim(
        min(min(success_rates) - 5, 90), 100
    )  # Set y-axis to focus on relevant range
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend()

    # Save chart
    output_path = Path(output_dir) / "success_rate_by_batch.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Generated success rate chart: {output_path}")


def generate_stage_time_chart(metrics, output_dir):
    """Generate a chart showing average processing time by pipeline stage."""
    stages = []
    avg_times = []

    for stage, stage_metrics in metrics["stage_metrics"].items():
        if "avg_time" in stage_metrics:
            stages.append(stage.capitalize())
            avg_times.append(stage_metrics["avg_time"])

    # Sort stages by average time (descending)
    sorted_data = sorted(zip(stages, avg_times), key=lambda x: x[1], reverse=True)
    stages, avg_times = zip(*sorted_data) if sorted_data else ([], [])

    plt.figure(figsize=(10, 6))
    bars = plt.bar(stages, avg_times, color="skyblue")

    # Add values above bars
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + 0.001,
            f"{height:.4f}s",
            ha="center",
            va="bottom",
            rotation=0,
        )

    plt.title("Average Processing Time by Pipeline Stage")
    plt.xlabel("Pipeline Stage")
    plt.ylabel("Average Time per Lead (seconds)")
    plt.grid(True, axis="y", linestyle="--", alpha=0.7)

    # Save chart
    output_path = Path(output_dir) / "stage_processing_time.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Generated stage processing time chart: {output_path}")


def generate_failure_rate_chart(metrics, output_dir):
    """Generate a chart showing failure rate by pipeline stage."""
    stages = []
    failure_rates = []

    for stage, stage_metrics in metrics["stage_metrics"].items():
        if "failure_rate" in stage_metrics:
            stages.append(stage.capitalize())
            failure_rates.append(
                stage_metrics["failure_rate"] * 100
            )  # Convert to percentage

    # Sort stages by failure rate (descending)
    sorted_data = sorted(zip(stages, failure_rates), key=lambda x: x[1], reverse=True)
    stages, failure_rates = zip(*sorted_data) if sorted_data else ([], [])

    plt.figure(figsize=(10, 6))
    bars = plt.bar(stages, failure_rates, color="salmon")

    # Add values above bars
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + 0.05,
            f"{height:.2f}%",
            ha="center",
            va="bottom",
            rotation=0,
        )

    plt.title("Failure Rate by Pipeline Stage")
    plt.xlabel("Pipeline Stage")
    plt.ylabel("Failure Rate (%)")
    plt.grid(True, axis="y", linestyle="--", alpha=0.7)

    # Save chart
    output_path = Path(output_dir) / "stage_failure_rate.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Generated failure rate chart: {output_path}")


def generate_processing_time_histogram(metrics, output_dir):
    """Generate a histogram of batch processing times."""
    processing_times = [batch["processing_time"] for batch in metrics["batches"]]

    plt.figure(figsize=(10, 6))
    plt.hist(processing_times, bins=10, alpha=0.7, color="purple")
    plt.axvline(
        x=sum(processing_times) / len(processing_times),
        color="r",
        linestyle="--",
        label=f"Mean: {sum(processing_times) / len(processing_times):.2f}s",
    )

    plt.title("Distribution of Batch Processing Times")
    plt.xlabel("Processing Time (seconds)")
    plt.ylabel("Frequency")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend()

    # Save chart
    output_path = Path(output_dir) / "processing_time_histogram.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Generated processing time histogram: {output_path}")


def generate_charts(metrics, output_dir):
    """Generate all performance charts."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Generate individual charts
    generate_throughput_chart(metrics, output_dir)
    generate_success_rate_chart(metrics, output_dir)
    generate_stage_time_chart(metrics, output_dir)
    generate_failure_rate_chart(metrics, output_dir)
    generate_processing_time_histogram(metrics, output_dir)

    # Generate summary dashboard
    generate_dashboard(metrics, output_dir)


def generate_dashboard(metrics, output_dir):
    """Generate a summary dashboard with multiple charts."""
    plt.figure(figsize=(15, 12))

    # Throughput by batch (top left)
    plt.subplot(2, 2, 1)
    batch_nums = [batch["batch_num"] for batch in metrics["batches"]]
    throughputs = [batch["throughput"] for batch in metrics["batches"]]
    plt.plot(batch_nums, throughputs, marker="o", linestyle="-", color="blue")
    avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0
    plt.axhline(
        y=avg_throughput, color="r", linestyle="--", label=f"Avg: {avg_throughput:.2f}"
    )
    plt.title("Throughput by Batch")
    plt.xlabel("Batch")
    plt.ylabel("Leads/second")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.7)

    # Success rate by batch (top right)
    plt.subplot(2, 2, 2)
    success_rates = [
        (
            (batch["success_count"] / batch["lead_count"]) * 100
            if batch["lead_count"] > 0
            else 0
        )
        for batch in metrics["batches"]
    ]
    plt.plot(batch_nums, success_rates, marker="o", linestyle="-", color="green")
    overall_success_rate = metrics["overall"]["success_rate"] * 100
    plt.axhline(
        y=overall_success_rate,
        color="r",
        linestyle="--",
        label=f"Overall: {overall_success_rate:.2f}%",
    )
    plt.title("Success Rate by Batch")
    plt.xlabel("Batch")
    plt.ylabel("Success Rate (%)")
    plt.ylim(min(min(success_rates) - 5, 90), 100)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.7)

    # Stage processing time (bottom left)
    plt.subplot(2, 2, 3)
    stages = []
    avg_times = []
    for stage, stage_metrics in metrics["stage_metrics"].items():
        if "avg_time" in stage_metrics:
            stages.append(stage.capitalize())
            avg_times.append(stage_metrics["avg_time"])
    sorted_data = sorted(zip(stages, avg_times), key=lambda x: x[1], reverse=True)
    stages, avg_times = zip(*sorted_data) if sorted_data else ([], [])
    plt.bar(stages, avg_times, color="skyblue")
    plt.title("Avg Time by Stage")
    plt.xlabel("Pipeline Stage")
    plt.ylabel("Seconds per Lead")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y", linestyle="--", alpha=0.7)

    # Failure rate by stage (bottom right)
    plt.subplot(2, 2, 4)
    stages = []
    failure_rates = []
    for stage, stage_metrics in metrics["stage_metrics"].items():
        if "failure_rate" in stage_metrics:
            stages.append(stage.capitalize())
            failure_rates.append(stage_metrics["failure_rate"] * 100)
    sorted_data = sorted(zip(stages, failure_rates), key=lambda x: x[1], reverse=True)
    stages, failure_rates = zip(*sorted_data) if sorted_data else ([], [])
    plt.bar(stages, failure_rates, color="salmon")
    plt.title("Failure Rate by Stage")
    plt.xlabel("Pipeline Stage")
    plt.ylabel("Failure Rate (%)")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y", linestyle="--", alpha=0.7)

    # Add overall title and adjust layout
    plt.suptitle(
        f"LeadFactory Performance Dashboard\nTotal Leads: {metrics.get('lead_count', 'N/A')}",
        fontsize=16,
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # Save dashboard
    output_path = Path(output_dir) / "performance_dashboard.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Generated performance dashboard: {output_path}")


if __name__ == "__main__":
    args = parse_args()

    try:
        metrics_file = find_latest_metrics_file(args.input_dir)
        metrics = load_metrics(metrics_file)
        generate_charts(metrics, args.output_dir)
        logger.info("Chart generation completed successfully")
    except Exception as e:
        logger.error(f"Error generating charts: {str(e)}")
        sys.exit(1)

    sys.exit(0)
