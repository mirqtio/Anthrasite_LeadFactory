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
        print("\n🔑 Running tests with REAL API calls where credentials are available")
        print("   Make sure you have added your API keys to the .env file\n")
    else:
        os.environ["LEADFACTORY_USE_REAL_APIS"] = "0"
        print("\n🧪 Running tests with MOCK API calls only\n")

    # Construct the pytest command
    cmd = ["pytest", "-xvs"]

    # Add API-specific test selection if specified
    if args.api:
        api_name = args.api.lower()
        print(f"📋 Running tests for {api_name.upper()} API only\n")
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
    print(f"🚀 Running command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=project_root)

    # Report summary
    if result.returncode == 0:
        print("\n✅ All API integration tests passed successfully!")
        if args.use_real_apis:
            print("   Real API calls were made where credentials were available.")
    else:
        print("\n❌ Some API integration tests failed.")
        print("   Please check the output above for details.")

        if args.use_real_apis:
            print("\n📋 If real API tests failed, check:")
            print("   1. Your API keys are correct in the .env file")
            print("   2. You have sufficient quota/credits for the API calls")
            print("   3. The API service is currently available")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
