#!/usr/bin/env python3
"""
API Integration Tests Runner

This script runs the API integration tests with the option to use real APIs.
It sets up the necessary environment variables and configuration for testing
with real external services.

Usage:
    python run_api_integration_tests.py [--use-real-apis] [--api=<api_name>]

Options:
    --use-real-apis    Run tests with real API calls where credentials are available
    --api=<api_name>   Run tests for a specific API only (e.g., yelp, google, openai)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    """Run API integration tests with real APIs if specified."""
    parser = argparse.ArgumentParser(description="Run API integration tests")
    parser.add_argument("--use-real-apis", action="store_true",
                        help="Run tests with real API calls where credentials are available")
    parser.add_argument("--api", type=str, default=None,
                        help="Run tests for a specific API only (e.g., yelp, google, openai)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output")

    args = parser.parse_args()

    # Determine the project root directory
    project_root = Path(__file__).parent.parent.absolute()

    # Set up environment for real API testing if requested
    if args.use_real_apis:
        os.environ["LEADFACTORY_USE_REAL_APIS"] = "1"
    else:
        os.environ["LEADFACTORY_USE_REAL_APIS"] = "0"

    # Construct the pytest command
    cmd = ["pytest", "-xvs"]

    # Add API-specific test selection if specified
    if args.api:
        api_name = args.api.lower()
        cmd.append(f"tests/integration/test_api_integrations.py::test_{api_name}")
    else:
        cmd.append("tests/integration/test_api_integrations.py")

    # Add verbose flag if specified
    if args.verbose:
        cmd.append("-v")

    # Add markers to run real API tests when requested
    if args.use_real_apis:
        cmd.append("-m")
        cmd.append("real_api")

    # Run the tests
    result = subprocess.run(cmd, cwd=project_root)

    # Report summary
    if result.returncode == 0:
        if args.use_real_apis:
            pass
    else:

        if args.use_real_apis:
            pass

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
