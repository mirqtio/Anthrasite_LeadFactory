"""
Configuration Validator Module

This module validates that all required environment variables are properly set
before running E2E tests. It checks for:
1. Core environment variables
2. API keys and credentials
3. Database connection parameters
4. Email and notification settings
5. Feature flags and toggles

Usage:
    from scripts.preflight.config_validator import ConfigValidator

    # Create validator
    validator = ConfigValidator()

    # Run validation
    result = validator.validate()

    if result.success:
        print("Configuration is valid!")
    else:
        print(f"Configuration validation failed: {result.message}")
        for issue in result.issues:
            print(f"- {issue}")
"""

import os
import sys
import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_E2E_FILE = PROJECT_ROOT / ".env.e2e"


@dataclass
class ValidationResult:
    """Result of a validation operation"""

    success: bool
    message: str
    issues: List[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class ConfigValidator:
    """
    Validates environment configuration for E2E testing

    This class checks that all required environment variables are properly set
    and contain valid values before running E2E tests.
    """

    # Required environment variables by category
    REQUIRED_VARS = {
        "core": [
            "ENVIRONMENT",
            "DEBUG_MODE",
            "LOG_LEVEL",
            "E2E_MODE",
            "MOCKUP_ENABLED",
        ],
        "database": ["DATABASE_URL"],
        "api_keys": ["OPENAI_API_KEY", "GOOGLE_MAPS_API_KEY", "SENDGRID_API_KEY"],
        "email": ["EMAIL_FROM", "EMAIL_OVERRIDE"],
        "pipeline": [
            "ENABLE_PIPELINE",
            "MAX_WORKERS",
            "RATE_LIMIT_REQUESTS",
            "RATE_LIMIT_PERIOD",
        ],
    }

    # Variables that must have specific values for E2E testing
    E2E_SPECIFIC_VALUES = {
        "ENVIRONMENT": "e2e_testing",
        "E2E_MODE": "true",
        "MOCKUP_ENABLED": "true",
        "DEBUG_MODE": "true",
    }

    # Variables with format validation
    FORMAT_VALIDATORS = {
        "DATABASE_URL": r"^postgresql://.*$",  # PostgreSQL connection string
        "EMAIL_FROM": r"^[^@]+@[^@]+\.[^@]+$",  # Email format
        "OPENAI_API_KEY": r"^sk-(proj-)?[A-Za-z0-9_-]{32,}$",  # OpenAI API key format (supports both old and new formats)
        "SENDGRID_API_KEY": r"^SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}$",  # SendGrid key format
    }

    def __init__(self, env_file: Optional[str] = None, check_all_vars: bool = False):
        """
        Initialize the config validator

        Args:
            env_file: Path to the environment file to validate (default: .env.e2e)
            check_all_vars: Whether to check all required variables or only those
                            needed for the current environment
        """
        self.env_file = Path(env_file) if env_file else ENV_E2E_FILE
        self.check_all_vars = check_all_vars
        self.env_vars = {}
        self.missing_vars = []
        self.invalid_vars = []

    def _load_env_file(self) -> bool:
        """Load environment variables from file"""
        if not self.env_file.exists():
            logger.error(f"Environment file not found: {self.env_file}")
            return False

        logger.info(f"Loading environment from {self.env_file}")

        try:
            # Parse environment file
            with open(self.env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    try:
                        key, value = line.split("=", 1)
                        self.env_vars[key.strip()] = value.strip()
                    except ValueError:
                        logger.warning(
                            f"Skipping invalid line in {self.env_file}: {line}"
                        )

            return True
        except Exception as e:
            logger.error(f"Error loading environment file: {e}")
            return False

    def _get_all_required_vars(self) -> Set[str]:
        """Get all required environment variables"""
        required_vars = set()
        for category, vars_list in self.REQUIRED_VARS.items():
            required_vars.update(vars_list)
        return required_vars

    def _check_vars_exist(self) -> bool:
        """Check if all required environment variables exist"""
        all_required = self._get_all_required_vars()
        self.missing_vars = []

        for var in all_required:
            # Skip API keys if MOCKUP_ENABLED is true and we're not checking all vars
            if (
                not self.check_all_vars
                and self.env_vars.get("MOCKUP_ENABLED", "").lower() == "true"
                and var in self.REQUIRED_VARS["api_keys"]
                and var != "OPENAI_API_KEY"
            ):  # Always require OpenAI key
                continue

            if var not in self.env_vars or not self.env_vars[var]:
                self.missing_vars.append(var)

        return len(self.missing_vars) == 0

    def _check_e2e_specific_values(self) -> bool:
        """Check if E2E-specific variables have the correct values"""
        if not self.check_all_vars:
            return True

        self.invalid_vars = []

        for var, expected_value in self.E2E_SPECIFIC_VALUES.items():
            if (
                var in self.env_vars
                and self.env_vars[var].lower() != expected_value.lower()
            ):
                self.invalid_vars.append(
                    f"{var} has value '{self.env_vars[var]}', expected '{expected_value}'"
                )

        return len(self.invalid_vars) == 0

    def _validate_formats(self) -> bool:
        """Validate format of environment variables"""
        for var, pattern in self.FORMAT_VALIDATORS.items():
            # Skip if variable is not present
            if var not in self.env_vars or not self.env_vars[var]:
                continue

            # Skip API keys if MOCKUP_ENABLED is true and we're not checking all vars
            if (
                not self.check_all_vars
                and self.env_vars.get("MOCKUP_ENABLED", "").lower() == "true"
                and var in self.REQUIRED_VARS["api_keys"]
                and var != "OPENAI_API_KEY"
            ):  # Always require OpenAI key
                continue

            value = self.env_vars[var]
            if not re.match(pattern, value):
                self.invalid_vars.append(f"{var} has invalid format: '{value}'")

        return len(self.invalid_vars) == 0

    def generate_sample_env_file(self, output_path: str) -> None:
        """Generate a sample .env file with required configuration variables.

        Args:
            output_path: Path to write the sample .env file to
        """
        logger.info(f"Generating sample configuration file at {output_path}")

        sample_config = """
# Configuration Variables for E2E Tests
# --------------------------------------

# Core Configuration
E2E_MODE=true
MOCKUP_ENABLED=false
ENVIRONMENT=test
APP_URL=http://localhost:3000
DEBUG=true

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory  # pragma: allowlist secret
DB_HOST=localhost
DB_PORT=5433
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=leadfactory

# API Keys
OPENAI_API_KEY=sk-test-xxxxxxxxxxxxxxxxxxxx
GOOGLE_MAPS_API_KEY=test-google-maps-key
SENDGRID_API_KEY=test-sendgrid-key

# Email Configuration
EMAIL_FROM=test@example.com
EMAIL_ADMIN=admin@example.com

# Pipeline Configuration
PIPELINE_ENABLED=true
PIPELINE_BATCH_SIZE=10
PIPELINE_CONCURRENCY=2
"""

        try:
            with open(output_path, "w") as f:
                f.write(sample_config.strip())
            logger.info(f"✅ Sample configuration written to {output_path}")
        except IOError as e:
            logger.error(f"Failed to write sample configuration: {str(e)}")

    def validate(self) -> ValidationResult:
        """
        Validate environment configuration

        Returns:
            ValidationResult object with success status, message, and issues
        """
        logger.info("Validating environment configuration...")

        # Load environment file
        if not self._load_env_file():
            return ValidationResult(
                success=False,
                message=f"Failed to load environment file: {self.env_file}",
                issues=[f"Environment file not found or not readable: {self.env_file}"],
            )

        # Check if required variables exist
        vars_exist = self._check_vars_exist()

        # Check if E2E-specific variables have the correct values
        e2e_values_valid = self._check_e2e_specific_values()

        # Validate format of variables
        formats_valid = self._validate_formats()

        # Combine all issues
        all_issues = []
        all_issues.extend(
            [f"Missing required variable: {var}" for var in self.missing_vars]
        )
        all_issues.extend(self.invalid_vars)

        # Return validation result
        if vars_exist and e2e_values_valid and formats_valid:
            logger.info("✅ Environment configuration is valid")
            return ValidationResult(
                success=True, message="Environment configuration is valid", issues=[]
            )
        else:
            logger.error("❌ Environment configuration is invalid")
            for issue in all_issues:
                logger.error(f"  - {issue}")

            return ValidationResult(
                success=False,
                message="Environment configuration is invalid",
                issues=all_issues,
            )

    def generate_sample_env(self, output_file: Optional[str] = None) -> bool:
        """
        Generate a sample environment file with all required variables

        Args:
            output_file: Path to write the sample environment file

        Returns:
            True if the file was successfully written
        """
        output_path = (
            Path(output_file) if output_file else self.env_file.with_suffix(".sample")
        )
        all_required = self._get_all_required_vars()

        try:
            with open(output_path, "w") as f:
                f.write("# Sample environment file for E2E testing\n")
                f.write("# Generated by ConfigValidator\n\n")

                # Write variables by category
                for category, vars_list in self.REQUIRED_VARS.items():
                    f.write(f"# {category.upper()} CONFIGURATION\n")
                    for var in vars_list:
                        if var in self.E2E_SPECIFIC_VALUES:
                            f.write(f"{var}={self.E2E_SPECIFIC_VALUES[var]}\n")
                        else:
                            f.write(f"{var}=\n")
                    f.write("\n")

            logger.info(f"✅ Generated sample environment file: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating sample environment file: {e}")
            return False


def main():
    """Command-line interface for the configuration validator"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate environment configuration for E2E testing"
    )
    parser.add_argument(
        "--env-file",
        help="Path to the environment file to validate (default: .env.e2e)",
    )
    parser.add_argument(
        "--check-all", action="store_true", help="Check all required variables"
    )
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate a sample environment file",
    )
    parser.add_argument("--output", help="Path to write the sample environment file")

    args = parser.parse_args()

    validator = ConfigValidator(env_file=args.env_file, check_all_vars=args.check_all)

    if args.generate_sample:
        success = validator.generate_sample_env(output_file=args.output)
        return 0 if success else 1

    result = validator.validate()

    if result.success:
        print("✅ Environment configuration is valid")
        return 0
    else:
        print(f"❌ Environment configuration is invalid: {result.message}")
        for issue in result.issues:
            print(f"  - {issue}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
