#!/usr/bin/env python
"""
E2E Test Runner for LeadFactory Pipeline

This script runs the E2E BDD test scenario that validates the full pipeline
with real API keys, including email delivery to a controlled address.
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def check_env_file():
    """Check if .env.e2e file exists and has required variables."""
    env_file = Path(__file__).resolve().parent.parent / ".env.e2e"
    if not env_file.exists():
        print("ERROR: .env.e2e file not found.")
        print(
            "Please create this file with your real API keys and EMAIL_OVERRIDE setting."
        )
        return False

    # Read file and check for key variables
    required_vars = [
        "EMAIL_OVERRIDE",
        "SENDGRID_API_KEY",
        "SCREENSHOT_ONE_API_KEY",
        "OPENAI_API_KEY",
        "YELP_API_KEY",
        "GOOGLE_API_KEY",
        "MOCKUP_ENABLED",
    ]

    with open(env_file, "r") as f:
        content = f.read()

    missing_vars = []
    for var in required_vars:
        if f"{var}=" not in content:
            missing_vars.append(var)

    if missing_vars:
        print(
            f"ERROR: Missing required variables in .env.e2e: {', '.join(missing_vars)}"
        )
        return False

    return True


def run_e2e_test():
    """Run the E2E BDD test scenario."""
    # Check if the environment file is properly configured
    if not check_env_file():
        sys.exit(1)

    # Change to the project root directory
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    # Set up logging directory
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"e2e_test_{time.strftime('%Y%m%d_%H%M%S')}.log"

    # Clear any existing summary file
    summary_file = Path("e2e_summary.md")
    if summary_file.exists():
        summary_file.unlink()

    print("===== Running E2E Test with Real API Keys =====")
    print("This test will use real API keys and send an actual email.")
    print(f"All emails will be redirected to the EMAIL_OVERRIDE address.")
    print(f"Logs will be saved to: {log_file}")
    print("Starting test in 3 seconds...")
    time.sleep(3)

    # Load environment variables from .env.e2e first to ensure they're available
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env.e2e", override=True)

    # Run the BDD test with the e2e tag and direct to a log file
    cmd = [
        "python3",
        "-m",
        "pytest",
        "tests/bdd/features/pipeline_stages.feature::Full lead processed and email delivered",
        "-v",
        "--no-header",
        "--capture=tee-sys",  # Capture output but also show it
        "--log-cli-level=INFO",  # Show logs in the console
        f"--log-file={log_file}",  # Also save logs to a file
        "-m",
        "e2e and real_api",  # Only run tests with both e2e and real_api markers
    ]

    try:
        print(f"\nExecuting: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Print the output
        print("\n===== Test Output =====")
        print(result.stdout)

        if result.stderr:
            print("\n===== Test Errors =====")
            print(result.stderr)

        # Check if the summary file was created
        if summary_file.exists():
            print("\n===== E2E Summary =====")
            with open(summary_file, "r") as f:
                print(f.read())
        else:
            print("\nWARNING: e2e_summary.md file was not created.")

        # Always check the logs for verification
        print(f"\n===== IMPORTANT: Review the complete logs at {log_file} =====")
        print(
            "These logs are critical for verifying test success and diagnosing any issues."
        )
        print(
            "Remember to check all external service responses and confirm email delivery."
        )

        if result.returncode != 0:
            print("\n❌ E2E test FAILED. Please review the logs for details.")
        else:
            print(
                "\n✅ E2E test PASSED. Please verify email delivery and check logs to confirm."
            )

        # Return the exit code
        return result.returncode
    except Exception as e:
        print(f"ERROR: Failed to run E2E test: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(run_e2e_test())
