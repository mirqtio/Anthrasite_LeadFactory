"""
API Connectivity Tester Module

This module validates connectivity to all required external APIs
before running E2E tests. It checks:
1. OpenAI API
2. Google Maps API
3. SendGrid API

Each API test performs a lightweight request to verify connectivity
and proper authentication without consuming significant resources.

Usage:
    from scripts.preflight.api_tester import ApiTester

    # Create tester
    tester = ApiTester()

    # Run all tests
    result = tester.test_all_apis()

    if result.success:
        print("All API connections are working!")
    else:
        print(f"API connectivity test failed: {result.message}")
        for issue in result.issues:
            print(f"- {issue}")

    # Or test individual APIs
    openai_result = tester.test_openai_api()
    maps_result = tester.test_google_maps_api()
    sendgrid_result = tester.test_sendgrid_api()
"""

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env.e2e"


@dataclass
class ApiTestResult:
    """Result of an API test operation"""

    success: bool
    api_name: str
    message: str
    response_data: Optional[dict[str, Any]] = None
    status_code: Optional[int] = None
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class ApiTester:
    """
    Tests connectivity to external APIs

    This class verifies that all required external APIs are accessible
    and properly authenticated before running E2E tests.
    """

    # API endpoints for testing
    OPENAI_TEST_URL = "https://api.openai.com/v1/models"
    GOOGLE_MAPS_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    SENDGRID_TEST_URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, env_file: Optional[str] = None, mock_mode: bool = False):
        """
        Initialize the API tester

        Args:
            env_file: Path to the environment file with API keys (default: .env.e2e)
            mock_mode: Whether to run in mock mode (no actual API calls)
        """
        self.env_file = Path(env_file) if env_file else ENV_FILE
        self.mock_mode = mock_mode
        self.api_keys = {}
        self.env_vars = {}
        self._load_api_keys()

    def _load_api_keys(self) -> None:
        """Load API keys from environment file"""
        # Initialize with empty values
        self.api_keys = {"openai": "", "google_maps": "", "sendgrid": ""}

        # Load from file first (takes priority)
        if self.env_file.exists():
            logger.info(f"Loading API keys from {self.env_file}")

            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    try:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Store all environment variables
                        self.env_vars[key.lower()] = value

                        if key == "OPENAI_API_KEY":
                            self.api_keys["openai"] = value
                        elif key == "GOOGLE_MAPS_API_KEY":
                            self.api_keys["google_maps"] = value
                        elif key == "SENDGRID_API_KEY":
                            self.api_keys["sendgrid"] = value
                    except ValueError:
                        continue

        # Fall back to environment variables only if not found in file
        if not self.api_keys["openai"]:
            self.api_keys["openai"] = os.getenv("OPENAI_API_KEY", "")
        if not self.api_keys["google_maps"]:
            self.api_keys["google_maps"] = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if not self.api_keys["sendgrid"]:
            self.api_keys["sendgrid"] = os.getenv("SENDGRID_API_KEY", "")

    def _is_mock_enabled(self) -> bool:
        """Check if mockup mode is enabled in environment or env file"""
        # First check environment variable
        mockup_enabled = os.getenv("MOCKUP_ENABLED", "").lower()

        # Then check environment file if not set in environment
        if not mockup_enabled and "mockup_enabled" in self.env_vars:
            mockup_enabled = self.env_vars.get("mockup_enabled", "").lower()

        return mockup_enabled in ("true", "1", "yes", "y") or self.mock_mode

    def test_openai_api(self) -> ApiTestResult:
        """
        Test OpenAI API connectivity

        Sends a lightweight request to the OpenAI API to verify connectivity
        and proper authentication.

        Returns:
            ApiTestResult with success status and response details
        """
        api_name = "OpenAI API"
        logger.info(f"Testing {api_name} connectivity...")

        # Skip test if mock mode is enabled
        if self._is_mock_enabled():
            logger.info(f"Skipping {api_name} test (mock mode enabled)")
            return ApiTestResult(
                success=True,
                api_name=api_name,
                message=f"{api_name} test skipped (mock mode enabled)",
            )

        # Check if API key is available
        api_key = self.api_keys.get("openai")
        if not api_key:
            logger.error(f"{api_name} key not found")
            return ApiTestResult(
                success=False,
                api_name=api_name,
                message=f"{api_name} key not found",
                issues=[f"{api_name} key not found in environment or {self.env_file}"],
            )

        try:
            # Send request to OpenAI API
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            response = requests.get(self.OPENAI_TEST_URL, headers=headers, timeout=10)

            # Check response
            if response.status_code == 200:
                logger.info(f"✅ {api_name} connection successful")
                return ApiTestResult(
                    success=True,
                    api_name=api_name,
                    message=f"{api_name} connection successful",
                    response_data=response.json(),
                    status_code=response.status_code,
                )
            else:
                error_message = (
                    f"{api_name} returned status code {response.status_code}"
                )
                logger.error(error_message)

                try:
                    error_details = response.json()
                    error_detail = error_details.get("error", {}).get(
                        "message", "Unknown error"
                    )
                    issues = [f"{api_name} error: {error_detail}"]
                except Exception:
                    issues = [error_message]

                return ApiTestResult(
                    success=False,
                    api_name=api_name,
                    message=error_message,
                    response_data=response.json() if response.text else None,
                    status_code=response.status_code,
                    issues=issues,
                )

        except requests.RequestException as e:
            error_message = f"{api_name} connection error: {str(e)}"
            logger.error(error_message)

            return ApiTestResult(
                success=False,
                api_name=api_name,
                message=error_message,
                issues=[error_message],
            )

    def test_google_maps_api(self) -> ApiTestResult:
        """
        Test Google Maps API connectivity

        Sends a lightweight request to the Google Maps Geocoding API to verify
        connectivity and proper authentication.

        Returns:
            ApiTestResult with success status and response details
        """
        api_name = "Google Maps API"
        logger.info(f"Testing {api_name} connectivity...")

        # Skip test if mock mode is enabled
        if self._is_mock_enabled():
            logger.info(f"Skipping {api_name} test (mock mode enabled)")
            return ApiTestResult(
                success=True,
                api_name=api_name,
                message=f"{api_name} test skipped (mock mode enabled)",
            )

        # Check if API key is available
        api_key = self.api_keys.get("google_maps")
        if not api_key:
            logger.error(f"{api_name} key not found")
            return ApiTestResult(
                success=False,
                api_name=api_name,
                message=f"{api_name} key not found",
                issues=[f"{api_name} key not found in environment or {self.env_file}"],
            )

        try:
            # Send request to Google Maps API
            params = {
                "address": "1600 Amphitheatre Parkway, Mountain View, CA",
                "key": api_key,
            }

            response = requests.get(
                self.GOOGLE_MAPS_GEOCODE_URL, params=params, timeout=10
            )

            # Check response
            if response.status_code == 200:
                response_data = response.json()

                if response_data.get("status") == "OK":
                    logger.info(f"✅ {api_name} connection successful")
                    return ApiTestResult(
                        success=True,
                        api_name=api_name,
                        message=f"{api_name} connection successful",
                        response_data=response_data,
                        status_code=response.status_code,
                    )
                else:
                    error_status = response_data.get("status", "UNKNOWN_ERROR")
                    error_message = f"{api_name} returned error status: {error_status}"
                    logger.error(error_message)

                    return ApiTestResult(
                        success=False,
                        api_name=api_name,
                        message=error_message,
                        response_data=response_data,
                        status_code=response.status_code,
                        issues=[f"{api_name} error: {error_status}"],
                    )
            else:
                error_message = (
                    f"{api_name} returned status code {response.status_code}"
                )
                logger.error(error_message)

                return ApiTestResult(
                    success=False,
                    api_name=api_name,
                    message=error_message,
                    response_data=response.json() if response.text else None,
                    status_code=response.status_code,
                    issues=[error_message],
                )

        except requests.RequestException as e:
            error_message = f"{api_name} connection error: {str(e)}"
            logger.error(error_message)

            return ApiTestResult(
                success=False,
                api_name=api_name,
                message=error_message,
                issues=[error_message],
            )

    def test_sendgrid_api(self) -> ApiTestResult:
        """
        Test SendGrid API connectivity

        Tests SendGrid API by validating the API key without sending an actual email.
        Uses the mail/send endpoint with a dry run validation request.

        Returns:
            ApiTestResult with success status and response details
        """
        api_name = "SendGrid API"
        logger.info(f"Testing {api_name} connectivity...")

        # Skip test if mock mode is enabled
        if self._is_mock_enabled():
            logger.info(f"Skipping {api_name} test (mock mode enabled)")
            return ApiTestResult(
                success=True,
                api_name=api_name,
                message=f"{api_name} test skipped (mock mode enabled)",
            )

        # Check if API key is available
        api_key = self.api_keys.get("sendgrid")
        if not api_key:
            logger.error(f"{api_name} key not found")
            return ApiTestResult(
                success=False,
                api_name=api_name,
                message=f"{api_name} key not found",
                issues=[f"{api_name} key not found in environment or {self.env_file}"],
            )

        try:
            # Use SendGrid API to validate email template
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # We're using an endpoint that doesn't actually send an email
            # but validates our authentication and access
            response = requests.get(
                "https://api.sendgrid.com/v3/templates", headers=headers, timeout=10
            )

            # Check response
            if response.status_code in (200, 201, 202):
                logger.info(f"✅ {api_name} connection successful")
                return ApiTestResult(
                    success=True,
                    api_name=api_name,
                    message=f"{api_name} connection successful",
                    response_data=response.json(),
                    status_code=response.status_code,
                )
            else:
                error_message = (
                    f"{api_name} returned status code {response.status_code}"
                )
                logger.error(error_message)

                try:
                    error_details = response.json()
                    error_detail = error_details.get("errors", [{}])[0].get(
                        "message", "Unknown error"
                    )
                    issues = [f"{api_name} error: {error_detail}"]
                except Exception:
                    issues = [error_message]

                return ApiTestResult(
                    success=False,
                    api_name=api_name,
                    message=error_message,
                    response_data=response.json() if response.text else None,
                    status_code=response.status_code,
                    issues=issues,
                )

        except requests.RequestException as e:
            error_message = f"{api_name} connection error: {str(e)}"
            logger.error(error_message)

            return ApiTestResult(
                success=False,
                api_name=api_name,
                message=error_message,
                issues=[error_message],
            )

    def test_all_apis(self) -> ApiTestResult:
        """
        Test all external APIs

        Tests connectivity to all required external APIs and aggregates results.

        Returns:
            ApiTestResult with overall success status and combined issues
        """
        logger.info("Testing all API connections...")

        # Define test functions and check if they should be skipped
        test_configs = [
            (self.test_openai_api, "SKIP_OPENAI_API"),
            (self.test_google_maps_api, "SKIP_GOOGLE_MAPS_API"),
            (self.test_sendgrid_api, "SKIP_SENDGRID_API"),
        ]

        # Run tests that are not skipped
        test_results = []
        for test_func, skip_var in test_configs:
            if os.getenv(skip_var, "").lower() == "true":
                api_name = (
                    test_func.__name__.replace("test_", "").replace("_", " ").title()
                )
                logger.info(f"⚠️ Skipping {api_name} test ({skip_var}=true)")
                # Add a successful result for skipped tests
                test_results.append(
                    ApiTestResult(
                        success=True,
                        api_name=api_name,
                        message=f"{api_name} test skipped",
                    )
                )
            else:
                test_results.append(test_func())

        # Check if all tests were successful
        all_successful = all(result.success for result in test_results)

        # Aggregate issues
        all_issues = []
        for result in test_results:
            if not result.success:
                all_issues.extend(result.issues)

        # Create overall result
        if all_successful:
            logger.info("✅ All API connections are working")
            return ApiTestResult(
                success=True,
                api_name="All APIs",
                message="All API connections are working",
            )
        else:
            failed_apis = [
                result.api_name for result in test_results if not result.success
            ]
            error_message = (
                f"API connectivity test failed for: {', '.join(failed_apis)}"
            )
            logger.error(error_message)

            return ApiTestResult(
                success=False,
                api_name="All APIs",
                message=error_message,
                issues=all_issues,
            )

    def generate_sample_env_file(self, output_path: str) -> None:
        """Generate a sample .env file with required API keys.

        Args:
            output_path: Path to write the sample .env file to
        """
        logger.info(f"Generating sample API configuration file at {output_path}")

        sample_config = """
# API Configuration for E2E Tests
# ------------------------------

# OpenAI API
OPENAI_API_KEY=sk-test-xxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=500

# Google Maps API
GOOGLE_MAPS_API_KEY=test-google-maps-key
GOOGLE_MAPS_REGION=US

# SendGrid API
SENDGRID_API_KEY=test-sendgrid-key
EMAIL_FROM=test@example.com
EMAIL_REPLY_TO=noreply@example.com

# API Testing Configuration
MOCKUP_ENABLED=false
E2E_MODE=true
"""

        try:
            with open(output_path, "w") as f:
                f.write(sample_config.strip())
            logger.info(f"✅ Sample API configuration written to {output_path}")
        except OSError as e:
            logger.error(f"Failed to write sample API configuration: {str(e)}")


def main():
    """Command-line interface for the API tester"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test API connectivity for E2E testing"
    )
    parser.add_argument(
        "--env-file",
        help="Path to the environment file with API keys (default: .env.e2e)",
    )
    parser.add_argument(
        "--mock", action="store_true", help="Run in mock mode (no actual API calls)"
    )
    parser.add_argument(
        "--api",
        choices=["all", "openai", "google", "sendgrid"],
        default="all",
        help="Specific API to test (default: all)",
    )

    args = parser.parse_args()

    # Create tester
    tester = ApiTester(env_file=args.env_file, mock_mode=args.mock)

    # Run tests
    if args.api == "all":
        result = tester.test_all_apis()
    elif args.api == "openai":
        result = tester.test_openai_api()
    elif args.api == "google":
        result = tester.test_google_maps_api()
    elif args.api == "sendgrid":
        result = tester.test_sendgrid_api()

    # Print results

    if result.success:
        pass
    else:
        for _issue in result.issues:
            pass

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
