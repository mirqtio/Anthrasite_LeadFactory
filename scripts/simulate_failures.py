#!/usr/bin/env python
"""
Failure Simulation Script for LeadFactory.

This script intentionally triggers various failure scenarios to test
the logging, metrics, and error handling capabilities of the LeadFactory pipeline.

Usage:
    python simulate_failures.py --scenario [scenario_name] --stage [pipeline_stage]

Scenarios:
    - network: Simulate network connectivity issues
    - timeout: Simulate operation timeouts
    - resource: Simulate resource exhaustion (memory, CPU)
    - data: Simulate data corruption or validation failures
    - api: Simulate external API failures
    - cascade: Simulate cascading failures across multiple components
    - random: Randomly select and trigger one of the above scenarios
    - all: Run through all failure scenarios sequentially

Pipeline Stages:
    - scrape: Simulate failures in the scraping stage
    - enrich: Simulate failures in the enrichment stage
    - score: Simulate failures in the scoring stage
    - dedupe: Simulate failures in the deduplication stage
    - email: Simulate failures in the email queue stage
    - all: Run the specified scenario across all pipeline stages
"""

import argparse
import logging
import os
import random
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Add the parent directory to the path to import leadfactory modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadfactory.utils.logging import LogContext, get_logger
from leadfactory.utils.metrics import (
    PIPELINE_DURATION,
    PIPELINE_ERRORS,
    PIPELINE_FAILURE_RATE,
    MetricsTimer,
    push_to_gateway,
    record_metric,
)

# Configure logger
logger = get_logger("failure_simulator")


class FailureSimulator:
    """Simulates various failure scenarios for testing purposes."""

    def __init__(self, stage: str):
        """
        Initialize the failure simulator.

        Args:
            stage: The pipeline stage to simulate failures for.
        """
        self.stage = stage
        self.failure_id = int(time.time())
        self.context = {
            "simulator_id": self.failure_id,
            "stage": stage,
            "simulation_type": "controlled",
        }
        logger.info(
            f"Initializing failure simulator for stage '{stage}'", extra=self.context
        )

    def _record_failure_metrics(self, scenario: str, error_type: str) -> None:
        """
        Record metrics for the simulated failure.

        Args:
            scenario: The failure scenario that was simulated.
            error_type: The type of error that occurred.
        """
        # Record the error in our metrics
        record_metric(
            PIPELINE_ERRORS,
            increment=1,
            stage=self.stage,
            error_type=error_type,
            scenario=scenario,
        )

        # Set a failure rate of 100% for this simulation
        record_metric(
            PIPELINE_FAILURE_RATE,
            value=1.0,
            operation=f"simulate_{scenario}",
            stage=self.stage,
        )

        # Push metrics to Prometheus gateway if configured
        try:
            push_to_gateway(job=f"failure_simulation_{self.failure_id}")
            logger.info(
                "Successfully pushed failure metrics to gateway",
                extra={**self.context, "scenario": scenario, "error_type": error_type},
            )
        except Exception as e:
            logger.error(
                f"Failed to push metrics to gateway: {str(e)}",
                extra={**self.context, "scenario": scenario, "error_type": error_type},
            )

    def network_failure(self) -> None:
        """Simulate network connectivity issues."""
        logger.info("Simulating network failure", extra=self.context)

        try:
            with LogContext(logger, operation="api_request", **self.context):
                with MetricsTimer(
                    PIPELINE_DURATION, stage=self.stage, operation="api_request"
                ):
                    # Simulate a network connection error
                    logger.debug(
                        "Attempting to connect to external service", extra=self.context
                    )
                    raise ConnectionError(
                        "Connection refused: simulated network failure"
                    )
        except ConnectionError as e:
            # Log the failure with structured context
            logger.error(
                f"Network error occurred: {str(e)}",
                extra={
                    **self.context,
                    "error_type": "network_error",
                    "connection_attempts": 3,
                    "last_error": str(e),
                },
            )
            self._record_failure_metrics("network", "connection_error")

    def timeout_failure(self) -> None:
        """Simulate operation timeouts."""
        logger.info("Simulating timeout failure", extra=self.context)

        try:
            with LogContext(logger, operation="long_running_operation", **self.context):
                with MetricsTimer(
                    PIPELINE_DURATION, stage=self.stage, operation="long_operation"
                ):
                    # Simulate a timeout
                    logger.debug("Starting long-running operation", extra=self.context)
                    raise TimeoutError("Operation timed out after 30 seconds")
        except TimeoutError as e:
            # Log the timeout with structured context
            logger.error(
                f"Timeout error occurred: {str(e)}",
                extra={
                    **self.context,
                    "error_type": "timeout",
                    "operation_timeout_seconds": 30,
                    "last_error": str(e),
                },
            )
            self._record_failure_metrics("timeout", "operation_timeout")

    def resource_failure(self) -> None:
        """Simulate resource exhaustion."""
        logger.info("Simulating resource exhaustion", extra=self.context)

        try:
            with (
                LogContext(logger, operation="resource_intensive_task", **self.context),
                MetricsTimer(
                    PIPELINE_DURATION, stage=self.stage, operation="resource_task"
                ),
            ):
                # Simulate memory exhaustion
                logger.debug("Allocating large amounts of memory", extra=self.context)
                raise MemoryError("Out of memory: simulated resource exhaustion")
        except MemoryError as e:
            # Log the resource failure with structured context
            logger.error(
                f"Resource error occurred: {str(e)}",
                extra={
                    **self.context,
                    "error_type": "resource_exhaustion",
                    "resource_type": "memory",
                    "last_error": str(e),
                },
            )
            self._record_failure_metrics("resource", "memory_error")

    def data_failure(self) -> None:
        """Simulate data corruption or validation failures."""
        logger.info("Simulating data validation failure", extra=self.context)

        try:
            with LogContext(logger, operation="data_processing", **self.context):
                with MetricsTimer(
                    PIPELINE_DURATION, stage=self.stage, operation="data_processing"
                ):
                    # Simulate data validation error
                    logger.debug("Validating input data", extra=self.context)
                    raise ValueError(
                        "Invalid data format: expected JSON, got corrupted data"
                    )
        except ValueError as e:
            # Log the data failure with structured context
            logger.error(
                f"Data validation error: {str(e)}",
                extra={
                    **self.context,
                    "error_type": "data_validation",
                    "expected_format": "json",
                    "validation_errors": ["missing_required_field", "invalid_format"],
                    "last_error": str(e),
                },
            )
            self._record_failure_metrics("data", "validation_error")

    def api_failure(self) -> None:
        """Simulate external API failures."""
        logger.info("Simulating external API failure", extra=self.context)

        try:
            with (
                LogContext(
                    logger,
                    operation="external_api_call",
                    service="mock_service",
                    **self.context,
                ),
                MetricsTimer(PIPELINE_DURATION, stage=self.stage, operation="api_call"),
            ):
                # Simulate API error response
                logger.debug("Calling external API", extra=self.context)
                error_response = {
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests, please try again later",
                    "status_code": 429,
                }
                raise RuntimeError(f"API request failed: {error_response}")
        except RuntimeError as e:
            # Log the API failure with structured context
            logger.error(
                f"External API error: {str(e)}",
                extra={
                    **self.context,
                    "error_type": "api_error",
                    "service": "mock_service",
                    "status_code": 429,
                    "retry_after": 60,
                    "last_error": str(e),
                },
            )
            self._record_failure_metrics("api", "rate_limit_exceeded")

    def cascade_failure(self) -> None:
        """Simulate cascading failures across multiple components."""
        logger.info("Simulating cascading failure", extra=self.context)

        def component_a():
            with LogContext(logger, component="ComponentA", **self.context):
                logger.debug("ComponentA starting", extra=self.context)
                return component_b()

        def component_b():
            with LogContext(logger, component="ComponentB", **self.context):
                logger.debug("ComponentB starting", extra=self.context)
                return component_c()

        def component_c():
            with LogContext(logger, component="ComponentC", **self.context):
                logger.debug("ComponentC starting", extra=self.context)
                raise RuntimeError(
                    "ComponentC failed: critical error in downstream service"
                )

        try:
            with (
                LogContext(
                    logger, operation="multi_component_operation", **self.context
                ),
                MetricsTimer(
                    PIPELINE_DURATION, stage=self.stage, operation="cascade_operation"
                ),
            ):
                component_a()
        except RuntimeError as e:
            # Log the cascading failure with structured context
            logger.error(
                f"Cascading failure: {str(e)}",
                extra={
                    **self.context,
                    "error_type": "cascade_failure",
                    "failing_component": "ComponentC",
                    "affected_components": ["ComponentA", "ComponentB", "ComponentC"],
                    "last_error": str(e),
                },
            )
            self._record_failure_metrics("cascade", "component_failure")

    def random_failure(self) -> None:
        """Randomly select and trigger one of the available failure scenarios."""
        # List of available failure scenarios
        scenarios = [
            self.network_failure,
            self.timeout_failure,
            self.resource_failure,
            self.data_failure,
            self.api_failure,
            self.cascade_failure,
        ]

        # Randomly select a scenario
        scenario = random.choice(scenarios)
        logger.info(
            f"Randomly selected failure scenario: {scenario.__name__}",
            extra=self.context,
        )

        # Execute the selected scenario
        scenario()

    def run_all_failures(self) -> None:
        """Run through all failure scenarios sequentially."""
        logger.info("Running all failure scenarios", extra=self.context)

        scenarios = [
            ("network", self.network_failure),
            ("timeout", self.timeout_failure),
            ("resource", self.resource_failure),
            ("data", self.data_failure),
            ("api", self.api_failure),
            ("cascade", self.cascade_failure),
        ]

        for name, scenario in scenarios:
            logger.info(f"Running '{name}' failure scenario", extra=self.context)
            try:
                scenario()
            except Exception as e:
                logger.error(
                    f"Unexpected error during '{name}' scenario: {str(e)}",
                    extra={
                        **self.context,
                        "scenario": name,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
            time.sleep(1)  # Small delay between scenarios

        logger.info("Completed all failure scenarios", extra=self.context)


def main() -> int:
    """
    Main entry point for the failure simulation script.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Simulate failures for testing")
    parser.add_argument(
        "--scenario",
        choices=[
            "network",
            "timeout",
            "resource",
            "data",
            "api",
            "cascade",
            "random",
            "all",
        ],
        default="random",
        help="Type of failure scenario to simulate",
    )
    parser.add_argument(
        "--stage",
        choices=["scrape", "enrich", "score", "dedupe", "email", "all"],
        default="all",
        help="Pipeline stage to simulate failures for",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )
    args = parser.parse_args()

    # Configure log level if specified
    if args.log_level:
        logger.setLevel(args.log_level)

    # Determine which stages to simulate failures for
    stages = (
        ["scrape", "enrich", "score", "dedupe", "email"]
        if args.stage == "all"
        else [args.stage]
    )

    try:
        for stage in stages:
            # Create a simulator for the current stage
            simulator = FailureSimulator(stage)

            # Run the requested failure scenario
            if args.scenario == "network":
                simulator.network_failure()
            elif args.scenario == "timeout":
                simulator.timeout_failure()
            elif args.scenario == "resource":
                simulator.resource_failure()
            elif args.scenario == "data":
                simulator.data_failure()
            elif args.scenario == "api":
                simulator.api_failure()
            elif args.scenario == "cascade":
                simulator.cascade_failure()
            elif args.scenario == "random":
                simulator.random_failure()
            elif args.scenario == "all":
                simulator.run_all_failures()

            # Add a small delay between stages
            if len(stages) > 1 and stage != stages[-1]:
                time.sleep(1)

        logger.info(
            "Failure simulation completed successfully",
            extra={"scenario": args.scenario, "stage": args.stage},
        )
        return 0
    except Exception as e:
        logger.error(
            f"Failure simulation script encountered an unexpected error: {str(e)}",
            extra={
                "error": str(e),
                "traceback": traceback.format_exc(),
                "scenario": args.scenario,
                "stage": args.stage,
            },
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
