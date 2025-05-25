#!/usr/bin/env python3
"""
Script to run large-scale validation of the LeadFactory pipeline.
This script processes a specified number of leads through the entire pipeline,
collecting performance metrics and validating system behavior at scale.
"""

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add parent directory to path so we can import from leadfactory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from leadfactory.pipeline import Pipeline
from leadfactory.utils.logging import setup_logger
from leadfactory.utils.metrics import (
    initialize_metrics,
    record_metric,
    PIPELINE_FAILURE_RATE,
)

# Configure logging
logger = setup_logger("large_scale_validation", level=logging.INFO)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run large-scale validation of the LeadFactory pipeline."
    )
    parser.add_argument(
        "--lead-count",
        type=int,
        default=10000,
        help="Number of leads to process (default: 10000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of leads to process in each batch (default: 100)",
    )
    parser.add_argument(
        "--generate-metrics",
        action="store_true",
        help="Generate detailed performance metrics",
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="performance_reports",
        help="Directory to store performance metrics (default: performance_reports)",
    )
    parser.add_argument(
        "--use-mocks", action="store_true", help="Use mock APIs for testing"
    )

    return parser.parse_args()


def generate_test_leads(count):
    """Generate test lead data for validation."""
    logger.info(f"Generating {count} test leads...")

    test_leads = []
    industries = [
        "restaurant",
        "retail",
        "healthcare",
        "technology",
        "education",
        "fitness",
    ]
    cities = [
        "New York",
        "Los Angeles",
        "Chicago",
        "Houston",
        "Phoenix",
        "Philadelphia",
    ]

    for i in range(count):
        lead = {
            "id": f"test-lead-{i+1}",
            "name": f"Test Business {i+1}",
            "industry": industries[i % len(industries)],
            "city": cities[i % len(cities)],
            "size": "small" if i % 3 == 0 else "medium" if i % 3 == 1 else "large",
            "contact_email": f"test{i+1}@example.com",
            "website": f"https://example-{i+1}.com",
        }
        test_leads.append(lead)

    return test_leads


def run_validation(args):
    """Run the large-scale validation."""
    start_time = time.time()
    metrics_dir = Path(args.metrics_dir)
    metrics_dir.mkdir(exist_ok=True, parents=True)

    logger.info(f"Starting large-scale validation with {args.lead_count} leads")

    # Initialize metrics collection
    initialize_metrics()

    # Generate test leads
    leads = generate_test_leads(args.lead_count)

    # Configure pipeline
    pipeline_config = {
        "use_mocks": args.use_mocks or os.environ.get("LEADFACTORY_USE_MOCKS") == "1",
        "throttle": os.environ.get("LEADFACTORY_THROTTLE_APIS") == "1",
    }

    # Create pipeline
    pipeline = Pipeline(**pipeline_config)

    # Process leads in batches
    total_processed = 0
    total_succeeded = 0
    total_failed = 0
    batch_times = []

    # Performance metrics
    performance_metrics = {
        "start_time": datetime.datetime.now().isoformat(),
        "lead_count": args.lead_count,
        "batch_size": args.batch_size,
        "batches": [],
        "stage_metrics": {
            "enrich": {"time": 0, "count": 0, "failures": 0},
            "score": {"time": 0, "count": 0, "failures": 0},
            "validate": {"time": 0, "count": 0, "failures": 0},
            "store": {"time": 0, "count": 0, "failures": 0},
        },
        "overall": {"time": 0, "throughput": 0, "success_rate": 0},
    }

    for i in range(0, len(leads), args.batch_size):
        batch_start = time.time()
        batch = leads[i : i + args.batch_size]
        batch_num = i // args.batch_size + 1

        logger.info(
            f"Processing batch {batch_num}/{(args.lead_count + args.batch_size - 1) // args.batch_size} ({len(batch)} leads)"
        )

        # Process batch
        batch_results = []
        for lead in batch:
            try:
                # Process each stage and track performance
                result = {"lead_id": lead["id"], "stages": {}}

                # Enrich stage
                stage_start = time.time()
                enriched = pipeline.enrich(lead)
                stage_time = time.time() - stage_start
                performance_metrics["stage_metrics"]["enrich"]["time"] += stage_time
                performance_metrics["stage_metrics"]["enrich"]["count"] += 1
                result["stages"]["enrich"] = {"success": True, "time": stage_time}

                # Score stage
                stage_start = time.time()
                scored = pipeline.score(enriched)
                stage_time = time.time() - stage_start
                performance_metrics["stage_metrics"]["score"]["time"] += stage_time
                performance_metrics["stage_metrics"]["score"]["count"] += 1
                result["stages"]["score"] = {"success": True, "time": stage_time}

                # Validate stage
                stage_start = time.time()
                validated = pipeline.validate(scored)
                stage_time = time.time() - stage_start
                performance_metrics["stage_metrics"]["validate"]["time"] += stage_time
                performance_metrics["stage_metrics"]["validate"]["count"] += 1
                result["stages"]["validate"] = {"success": True, "time": stage_time}

                # Store stage
                stage_start = time.time()
                stored = pipeline.store(validated)
                stage_time = time.time() - stage_start
                performance_metrics["stage_metrics"]["store"]["time"] += stage_time
                performance_metrics["stage_metrics"]["store"]["count"] += 1
                result["stages"]["store"] = {"success": True, "time": stage_time}

                # Lead succeeded
                total_succeeded += 1
                result["success"] = True

            except Exception as e:
                logger.error(f"Failed to process lead {lead['id']}: {str(e)}")
                total_failed += 1
                if "stages" not in result:
                    result["stages"] = {}
                result["success"] = False
                result["error"] = str(e)

                # Update failure metrics
                for stage in ["enrich", "score", "validate", "store"]:
                    if stage not in result["stages"]:
                        performance_metrics["stage_metrics"][stage]["failures"] += 1
                        break

                # Record failure metric
                record_metric(PIPELINE_FAILURE_RATE, 1)

            batch_results.append(result)
            total_processed += 1

        # Calculate batch metrics
        batch_time = time.time() - batch_start
        batch_times.append(batch_time)

        batch_metrics = {
            "batch_num": batch_num,
            "lead_count": len(batch),
            "processing_time": batch_time,
            "throughput": len(batch) / batch_time if batch_time > 0 else 0,
            "success_count": sum(1 for r in batch_results if r.get("success", False)),
            "failure_count": sum(
                1 for r in batch_results if not r.get("success", False)
            ),
        }

        performance_metrics["batches"].append(batch_metrics)

        logger.info(
            f"Batch {batch_num} processed in {batch_time:.2f}s "
            f"({batch_metrics['throughput']:.2f} leads/second, "
            f"{batch_metrics['success_count']}/{len(batch)} succeeded)"
        )

    # Calculate overall metrics
    total_time = time.time() - start_time

    performance_metrics["overall"]["time"] = total_time
    performance_metrics["overall"]["throughput"] = (
        args.lead_count / total_time if total_time > 0 else 0
    )
    performance_metrics["overall"]["success_rate"] = (
        total_succeeded / args.lead_count if args.lead_count > 0 else 0
    )
    performance_metrics["end_time"] = datetime.datetime.now().isoformat()

    # Calculate average times for each stage
    for stage, metrics in performance_metrics["stage_metrics"].items():
        if metrics["count"] > 0:
            metrics["avg_time"] = metrics["time"] / metrics["count"]
            metrics["failure_rate"] = metrics["failures"] / args.lead_count

    # Log summary
    logger.info(f"Validation completed in {total_time:.2f}s")
    logger.info(
        f"Processed {total_processed} leads: {total_succeeded} succeeded, {total_failed} failed"
    )
    logger.info(
        f"Overall throughput: {performance_metrics['overall']['throughput']:.2f} leads/second"
    )
    logger.info(
        f"Success rate: {performance_metrics['overall']['success_rate'] * 100:.2f}%"
    )

    # Write metrics to file if requested
    if args.generate_metrics:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_file = metrics_dir / f"validation_metrics_{timestamp}.json"

        with open(metrics_file, "w") as f:
            json.dump(performance_metrics, f, indent=2)

        logger.info(f"Performance metrics written to {metrics_file}")

    return total_succeeded, total_failed, performance_metrics


if __name__ == "__main__":
    args = parse_args()
    succeeded, failed, metrics = run_validation(args)

    # Exit with non-zero code if failure rate is too high
    max_allowed_failure_rate = 0.01  # 1%
    failure_rate = failed / args.lead_count if args.lead_count > 0 else 0

    if failure_rate > max_allowed_failure_rate:
        logger.error(
            f"Validation failed: Failure rate {failure_rate:.2%} exceeds maximum allowed {max_allowed_failure_rate:.2%}"
        )
        sys.exit(1)

    logger.info("Validation successful!")
    sys.exit(0)
