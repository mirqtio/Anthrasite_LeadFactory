#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline Component Validator

This module verifies that all pipeline services and components are properly
configured and operational before running E2E tests.
"""

import os
import re
import json
import logging
import subprocess
import requests
from dotenv import load_dotenv
from typing import List, Dict, Tuple, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PipelineValidationResult:
    """Result of pipeline component validation."""

    def __init__(
        self,
        success: bool,
        components_verified: List[str],
        components_failed: List[str],
        issues: List[str],
    ):
        self.success = success
        self.components_verified = components_verified
        self.components_failed = components_failed
        self.issues = issues

    def __str__(self) -> str:
        """String representation of the validation result."""
        if self.success:
            return "✅ Pipeline component validation successful"

        result = "❌ Pipeline component validation failed\n"
        for issue in self.issues:
            result += f"  - {issue}\n"
        return result


class PipelineValidator:
    """Validates pipeline components for E2E testing."""

    # Define required pipeline components
    REQUIRED_COMPONENTS = [
        "data_ingestion",
        "data_processing",
        "model_training",
        "api_gateway",
        "notification_service",
    ]

    def __init__(self, env_file: Optional[str] = None):
        """Initialize the pipeline validator.

        Args:
            env_file: Path to .env file to load environment variables from
        """
        self.env_file = env_file
        if env_file:
            logger.info(f"Loading pipeline configuration from {env_file}")
            load_dotenv(env_file)

        # Check if we're in mock mode
        self.mock_mode = os.getenv("MOCKUP_ENABLED", "false").lower() == "true"
        if self.mock_mode:
            logger.info("Running in mock mode - pipeline checks will be simulated")

    def validate(self) -> PipelineValidationResult:
        """Validate all pipeline components.

        Returns:
            PipelineValidationResult: Result of the validation
        """
        logger.info("Starting pipeline component validation...")

        components_verified = []
        components_failed = []
        issues = []

        # Check if we're in E2E mode
        e2e_mode = os.getenv("E2E_MODE", "false").lower() == "true"
        if not e2e_mode and not self.mock_mode:
            logger.warning("Not in E2E mode - skipping actual pipeline validation")
            return PipelineValidationResult(True, ["skipped_validation"], [], [])

        # In mock mode, simulate successful validation
        if self.mock_mode:
            logger.info("Mock mode: Simulating successful pipeline validation")
            return PipelineValidationResult(True, self.REQUIRED_COMPONENTS, [], [])

        # Verify each pipeline component
        for component in self.REQUIRED_COMPONENTS:
            success, component_issues = self._verify_component(component)
            if success:
                components_verified.append(component)
            else:
                components_failed.append(component)
                issues.extend(component_issues)

        # Overall success if all components verified
        success = len(components_failed) == 0

        if success:
            logger.info("✅ Pipeline component validation successful")
        else:
            logger.error("❌ Pipeline component validation failed")
            for issue in issues:
                logger.error(f"  - {issue}")

        return PipelineValidationResult(
            success, components_verified, components_failed, issues
        )

    def _verify_component(self, component: str) -> Tuple[bool, List[str]]:
        """Verify a single pipeline component.

        Args:
            component: Name of the component to verify

        Returns:
            Tuple of (success, list of issues)
        """
        logger.info(f"Verifying pipeline component: {component}")
        issues = []

        # Get component-specific environment variables
        component_url = os.getenv(f"{component.upper()}_URL")
        component_port = os.getenv(f"{component.upper()}_PORT")
        component_status_endpoint = os.getenv(
            f"{component.upper()}_STATUS_ENDPOINT", "/status"
        )

        # Check if required environment variables are set
        if not component_url:
            issues.append(f"Missing {component.upper()}_URL environment variable")
            return False, issues

        # Build the component endpoint URL
        endpoint = component_url
        if component_port:
            # If URL already has a port, don't add another one
            if not re.search(r":\d+", endpoint):
                endpoint = f"{endpoint}:{component_port}"

        # Add status endpoint if URL doesn't already end with it
        if not endpoint.endswith(component_status_endpoint):
            endpoint = f"{endpoint}{component_status_endpoint}"

        # Test connectivity to the component
        try:
            logger.info(f"Testing connectivity to {component} at {endpoint}")
            response = requests.get(endpoint, timeout=5)

            if response.status_code != 200:
                issues.append(
                    f"{component} returned status code {response.status_code}"
                )
                return False, issues

            # Parse and validate response content
            try:
                status_data = response.json()

                if "status" not in status_data:
                    issues.append(f"{component} response missing 'status' field")
                    return False, issues

                if status_data["status"] != "ok":
                    issues.append(
                        f"{component} status is '{status_data['status']}', not 'ok'"
                    )
                    return False, issues

                logger.info(f"✅ {component} is operational")
                return True, []

            except json.JSONDecodeError:
                issues.append(f"{component} returned invalid JSON response")
                return False, issues

        except requests.exceptions.RequestException as e:
            issues.append(f"Failed to connect to {component}: {str(e)}")
            return False, issues

    def verify_docker_services(self) -> Tuple[bool, List[str], List[str]]:
        """Verify that required Docker services are running.

        Returns:
            Tuple of (success, running services, issues)
        """
        logger.info("Verifying Docker services...")

        if self.mock_mode:
            logger.info("Mock mode: Simulating Docker services check")
            return True, self.REQUIRED_COMPONENTS, []

        running_services = []
        issues = []

        try:
            # Check if Docker is installed and running
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True,
            )

            # Get the list of running containers
            containers = result.stdout.strip().split("\n")
            containers = [c for c in containers if c]  # Remove empty entries

            # Check if our required components are running
            for component in self.REQUIRED_COMPONENTS:
                # Look for containers with component name in their name
                matching_containers = [
                    c for c in containers if component.lower() in c.lower()
                ]

                if matching_containers:
                    running_services.append(component)
                    logger.info(
                        f"✅ Found Docker container for {component}: {matching_containers[0]}"
                    )
                else:
                    issues.append(f"No Docker container found for {component}")
                    logger.error(f"❌ No Docker container found for {component}")

            success = len(issues) == 0
            return success, running_services, issues

        except subprocess.SubprocessError as e:
            logger.error(f"Error verifying Docker services: {str(e)}")
            issues.append(f"Error checking Docker services: {str(e)}")
            return False, running_services, issues
        except FileNotFoundError:
            logger.error("Docker command not found. Is Docker installed?")
            issues.append("Docker command not found. Is Docker installed?")
            return False, running_services, issues

    def verify_pipeline_connections(self) -> Tuple[bool, List[str]]:
        """Verify that all pipeline components can communicate with each other.

        Returns:
            Tuple of (success, issues)
        """
        logger.info("Verifying pipeline component connections...")

        if self.mock_mode:
            logger.info("Mock mode: Simulating pipeline connections check")
            return True, []

        issues = []

        # Define expected connections between components
        connections = [
            ("data_ingestion", "data_processing"),
            ("data_processing", "model_training"),
            ("model_training", "api_gateway"),
            ("api_gateway", "notification_service"),
        ]

        # Verify each connection
        for source, target in connections:
            logger.info(f"Checking connection: {source} -> {target}")

            source_url = os.getenv(f"{source.upper()}_URL")
            target_url = os.getenv(f"{target.upper()}_URL")

            if not source_url or not target_url:
                issues.append(f"Missing URL for {source} or {target}")
                continue

            # Check connection diagnostics endpoint if available
            diag_endpoint = os.getenv(
                f"{source.upper()}_DIAGNOSTICS_ENDPOINT", "/diagnostics"
            )
            full_endpoint = f"{source_url}{diag_endpoint}"

            try:
                response = requests.get(full_endpoint, timeout=5)

                if response.status_code != 200:
                    issues.append(
                        f"Failed to get diagnostics from {source}: status {response.status_code}"
                    )
                    continue

                try:
                    diag_data = response.json()

                    # Check if diagnostics data includes connection to target
                    connections_data = diag_data.get("connections", {})
                    target_connection = next(
                        (
                            c
                            for c in connections_data
                            if c.get("target", "").lower() == target.lower()
                        ),
                        None,
                    )

                    if not target_connection:
                        issues.append(
                            f"No connection data found from {source} to {target}"
                        )
                        continue

                    connection_status = target_connection.get("status")
                    if connection_status != "ok":
                        issues.append(
                            f"Connection from {source} to {target} has status '{connection_status}'"
                        )
                    else:
                        logger.info(f"✅ Connection verified: {source} -> {target}")

                except (json.JSONDecodeError, KeyError) as e:
                    issues.append(f"Invalid diagnostics data from {source}: {str(e)}")

            except requests.exceptions.RequestException as e:
                issues.append(
                    f"Failed to check connection {source} -> {target}: {str(e)}"
                )

        success = len(issues) == 0

        if success:
            logger.info("✅ All pipeline connections verified")
        else:
            logger.error("❌ Some pipeline connections failed")
            for issue in issues:
                logger.error(f"  - {issue}")

        return success, issues

    def generate_sample_env_file(self, output_path: str) -> None:
        """Generate a sample .env file with required pipeline configuration.

        Args:
            output_path: Path to write the sample .env file to
        """
        logger.info(f"Generating sample pipeline configuration file at {output_path}")

        sample_config = """
# Pipeline Component Configuration for E2E Tests
# ---------------------------------------------

# Global Settings
E2E_MODE=true
MOCKUP_ENABLED=false

# Data Ingestion Service
DATA_INGESTION_URL=http://localhost:8001
DATA_INGESTION_PORT=8001
DATA_INGESTION_STATUS_ENDPOINT=/status
DATA_INGESTION_DIAGNOSTICS_ENDPOINT=/diagnostics

# Data Processing Service
DATA_PROCESSING_URL=http://localhost:8002
DATA_PROCESSING_PORT=8002
DATA_PROCESSING_STATUS_ENDPOINT=/status
DATA_PROCESSING_DIAGNOSTICS_ENDPOINT=/diagnostics

# Model Training Service
MODEL_TRAINING_URL=http://localhost:8003
MODEL_TRAINING_PORT=8003
MODEL_TRAINING_STATUS_ENDPOINT=/status
MODEL_TRAINING_DIAGNOSTICS_ENDPOINT=/diagnostics

# API Gateway
API_GATEWAY_URL=http://localhost:8000
API_GATEWAY_PORT=8000
API_GATEWAY_STATUS_ENDPOINT=/status
API_GATEWAY_DIAGNOSTICS_ENDPOINT=/diagnostics

# Notification Service
NOTIFICATION_SERVICE_URL=http://localhost:8004
NOTIFICATION_SERVICE_PORT=8004
NOTIFICATION_SERVICE_STATUS_ENDPOINT=/status
NOTIFICATION_SERVICE_DIAGNOSTICS_ENDPOINT=/diagnostics
"""

        try:
            with open(output_path, "w") as f:
                f.write(sample_config.strip())
            logger.info(f"✅ Sample pipeline configuration written to {output_path}")
        except IOError as e:
            logger.error(f"Failed to write sample configuration: {str(e)}")


if __name__ == "__main__":
    # Example usage
    validator = PipelineValidator()
    result = validator.validate()
    print(result)
