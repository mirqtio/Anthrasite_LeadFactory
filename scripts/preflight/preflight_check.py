#!/usr/bin/env python3
"""
E2E Preflight Check System

This module integrates all preflight check components to validate the environment
configuration, API connectivity, database access, and pipeline services before
running E2E tests.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from scripts.preflight.api_tester import ApiTester

# Import preflight check components
from scripts.preflight.config_validator import ConfigValidator
from scripts.preflight.db_verifier import DbVerifier
from scripts.preflight.pipeline_validator import (
    PipelineValidationResult,
    PipelineValidator,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PreflightCheckResult:
    """Result of the E2E preflight check."""

    def __init__(self):
        self.config_validation = None
        self.api_tests = None
        self.db_verification = None
        self.pipeline_validation = None
        self.start_time = datetime.now()
        self.end_time = None
        self.success = False
        self.issues = []

    def complete(self, success: bool, issues: list[str]):
        """Complete the preflight check result."""
        self.end_time = datetime.now()
        self.success = success
        self.issues = issues

    def duration(self) -> float:
        """Calculate the duration of the preflight check in seconds."""
        if not self.end_time:
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    def __str__(self) -> str:
        """String representation of the preflight check result."""
        duration = self.duration()

        if self.success:
            return f"✅ E2E Preflight Check PASSED in {duration:.2f} seconds"

        result = f"❌ E2E Preflight Check FAILED in {duration:.2f} seconds\n"
        for issue in self.issues:
            result += f"  - {issue}\n"
        return result


class PreflightCheck:
    """E2E Preflight Check System for validating the test environment."""

    def __init__(self, env_file: Optional[str] = None, log_file: Optional[str] = None):
        """Initialize the preflight check system.

        Args:
            env_file: Path to .env file to load environment variables from
            log_file: Path to log file to write results to
        """
        self.env_file = env_file
        self.log_file = log_file

        # Initialize components
        self.config_validator = ConfigValidator(env_file)
        self.api_tester = ApiTester(env_file)
        self.db_verifier = DbVerifier(env_file)
        self.pipeline_validator = PipelineValidator(env_file)

        # Setup logging to file if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(file_handler)

        # Set up the result object
        self.result = PreflightCheckResult()

    def run(self) -> PreflightCheckResult:
        """Run all preflight checks.

        Returns:
            PreflightCheckResult: Result of the preflight check
        """
        logger.info("==========================================")
        logger.info("Starting E2E Preflight Check")
        logger.info("==========================================")

        if self.env_file:
            logger.info(f"Using environment file: {self.env_file}")

        # Track overall success and collect all issues
        success = True
        all_issues = []

        # Check configuration
        logger.info("\n[1/4] Checking Configuration...")
        config_result = self.config_validator.validate()
        self.result.config_validation = config_result

        if not config_result.success:
            success = False
            all_issues.extend(
                [f"Configuration: {issue}" for issue in config_result.issues]
            )
            logger.error("❌ Configuration validation failed")
        else:
            logger.info("✅ Configuration validation passed")

        # Check API connectivity
        logger.info("\n[2/4] Checking API Connectivity...")
        api_result = self.api_tester.test_all_apis()
        self.result.api_tests = api_result

        if not api_result.success:
            success = False
            all_issues.extend([f"API: {issue}" for issue in api_result.issues])
            logger.error("❌ API connectivity tests failed")
        else:
            logger.info("✅ API connectivity tests passed")

        # Check database connectivity
        logger.info("\n[3/4] Checking Database Connectivity...")
        db_result = self.db_verifier.verify_database()
        self.result.db_verification = db_result

        if not db_result.success:
            success = False
            all_issues.extend([f"Database: {issue}" for issue in db_result.issues])
            logger.error("❌ Database verification failed")
        else:
            logger.info("✅ Database verification passed")

        # Check pipeline components
        logger.info("\n[4/4] Checking Pipeline Components...")

        # Check if pipeline validation should be skipped
        skip_pipeline = os.getenv("SKIP_PIPELINE_VALIDATION", "").lower() == "true"
        if skip_pipeline:
            logger.info(
                "⚠️ Skipping pipeline component validation (SKIP_PIPELINE_VALIDATION=true)"
            )
            pipeline_result = PipelineValidationResult(
                success=True, components_verified=[], components_failed=[], issues=[]
            )
        else:
            pipeline_result = self.pipeline_validator.validate()

        self.result.pipeline_validation = pipeline_result

        if not pipeline_result.success:
            success = False
            all_issues.extend(
                [f"Pipeline: {issue}" for issue in pipeline_result.issues]
            )
            logger.error("❌ Pipeline component validation failed")
        else:
            logger.info("✅ Pipeline component validation passed")

        # Complete the result
        self.result.complete(success, all_issues)

        # Log final result
        logger.info("\n==========================================")
        if success:
            logger.info("✅ E2E Preflight Check PASSED")
            logger.info(f"Duration: {self.result.duration():.2f} seconds")
        else:
            logger.error("❌ E2E Preflight Check FAILED")
            logger.error(f"Duration: {self.result.duration():.2f} seconds")
            for issue in all_issues:
                logger.error(f"  - {issue}")
        logger.info("==========================================")

        return self.result

    def generate_report(self, output_file: str) -> None:
        """Generate a detailed report of the preflight check results.

        Args:
            output_file: Path to write the report to
        """
        if not self.result.end_time:
            logger.warning("Cannot generate report before preflight check is complete")
            return

        logger.info(f"Generating preflight check report: {output_file}")

        with open(output_file, "w") as f:
            f.write("E2E Preflight Check Report\n")
            f.write("=========================\n\n")
            f.write(f"Date: {self.result.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {self.result.duration():.2f} seconds\n")
            f.write(
                f"Overall Result: {'PASSED' if self.result.success else 'FAILED'}\n\n"
            )

            # Configuration Validation
            f.write("1. Configuration Validation\n")
            f.write("---------------------------\n")
            if self.result.config_validation:
                f.write(
                    f"Result: {'PASSED' if self.result.config_validation.success else 'FAILED'}\n"
                )
                if not self.result.config_validation.success:
                    f.write("Issues:\n")
                    for issue in self.result.config_validation.issues:
                        f.write(f"  - {issue}\n")
            else:
                f.write("Result: Not executed\n")
            f.write("\n")

            # API Connectivity
            f.write("2. API Connectivity Tests\n")
            f.write("-------------------------\n")
            if self.result.api_tests:
                api_success = all(
                    result.success for result in self.result.api_tests.values()
                )
                f.write(f"Result: {'PASSED' if api_success else 'FAILED'}\n")
                for api_name, api_result in self.result.api_tests.items():
                    status = "✓" if api_result.success else "✗"
                    f.write(f"  {status} {api_name}: {api_result.message}\n")
            else:
                f.write("Result: Not executed\n")
            f.write("\n")

            # Database Verification
            f.write("3. Database Verification\n")
            f.write("------------------------\n")
            if self.result.db_verification:
                f.write(
                    f"Result: {'PASSED' if self.result.db_verification.success else 'FAILED'}\n"
                )
                if not self.result.db_verification.success:
                    f.write("Issues:\n")
                    for issue in self.result.db_verification.issues:
                        f.write(f"  - {issue}\n")
            else:
                f.write("Result: Not executed\n")
            f.write("\n")

            # Pipeline Component Validation
            f.write("4. Pipeline Component Validation\n")
            f.write("--------------------------------\n")
            if self.result.pipeline_validation:
                f.write(
                    f"Result: {'PASSED' if self.result.pipeline_validation.success else 'FAILED'}\n"
                )

                if self.result.pipeline_validation.components_verified:
                    f.write("Verified Components:\n")
                    for (
                        component
                    ) in self.result.pipeline_validation.components_verified:
                        f.write(f"  - {component}\n")

                if self.result.pipeline_validation.components_failed:
                    f.write("Failed Components:\n")
                    for component in self.result.pipeline_validation.components_failed:
                        f.write(f"  - {component}\n")

                if self.result.pipeline_validation.issues:
                    f.write("Issues:\n")
                    for issue in self.result.pipeline_validation.issues:
                        f.write(f"  - {issue}\n")
            else:
                f.write("Result: Not executed\n")
            f.write("\n")

            # Summary
            f.write("Summary\n")
            f.write("-------\n")
            if self.result.success:
                f.write(
                    "✅ All preflight checks passed. The environment is ready for E2E testing.\n"
                )
            else:
                f.write(
                    "❌ Some preflight checks failed. The environment is not properly configured for E2E testing.\n"
                )
                f.write("Issues that need to be resolved:\n")
                for issue in self.result.issues:
                    f.write(f"  - {issue}\n")

        logger.info(f"Preflight check report generated: {output_file}")


def main():
    """Main entry point for the preflight check system."""
    parser = argparse.ArgumentParser(description="E2E Preflight Check System")
    parser.add_argument(
        "--env", type=str, help="Path to .env file with environment variables"
    )
    parser.add_argument(
        "--log", type=str, help="Path to log file for preflight check results"
    )
    parser.add_argument("--report", type=str, help="Path to output report file")
    parser.add_argument(
        "--generate-sample-env",
        action="store_true",
        help="Generate sample .env files for all components",
    )
    args = parser.parse_args()

    if args.generate_sample_env:
        generate_sample_env_files()
        return

    # Run preflight check
    preflight = PreflightCheck(env_file=args.env, log_file=args.log)
    result = preflight.run()

    # Generate report if requested
    if args.report:
        preflight.generate_report(args.report)

    # Set exit code based on result
    sys.exit(0 if result.success else 1)


def generate_sample_env_files():
    """Generate sample .env files for all components."""
    logger.info("Generating sample environment files for E2E testing...")

    # Generate config sample
    config_validator = ConfigValidator()
    config_validator.generate_sample_env_file("sample_config.env")

    # Generate API sample
    api_tester = ApiTester()
    api_tester.generate_sample_env_file("sample_api.env")

    # Generate DB sample
    db_verifier = DbVerifier()
    db_verifier.generate_sample_env_file("sample_db.env")

    # Generate Pipeline sample
    pipeline_validator = PipelineValidator()
    pipeline_validator.generate_sample_env_file("sample_pipeline.env")

    # Generate combined sample
    with open("sample_e2e.env", "w") as f:
        f.write("# Sample Environment Configuration for E2E Testing\n")
        f.write("# =============================================\n")
        f.write(
            "# This file combines all required environment variables for E2E testing.\n\n"
        )

        # Add content from each component sample
        for sample_file in [
            "sample_config.env",
            "sample_api.env",
            "sample_db.env",
            "sample_pipeline.env",
        ]:
            with open(sample_file) as component_file:
                f.write(f"\n# From {sample_file}\n")
                f.write(component_file.read())
                f.write("\n")

    logger.info("✅ Sample environment files generated:")
    logger.info("  - sample_config.env: Configuration variables")
    logger.info("  - sample_api.env: API connectivity variables")
    logger.info("  - sample_db.env: Database connectivity variables")
    logger.info("  - sample_pipeline.env: Pipeline component variables")
    logger.info("  - sample_e2e.env: Combined environment file")


if __name__ == "__main__":
    main()
