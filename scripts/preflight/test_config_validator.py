#!/usr/bin/env python3
"""
Test Script for Configuration Validator

This script tests the functionality of the ConfigValidator module,
ensuring it correctly identifies missing, invalid, or misconfigured
environment variables.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the config validator
from scripts.preflight.config_validator import ConfigValidator, ValidationResult

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_env_file(content):
    """Create a temporary environment file with the given content"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".env")
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


def test_valid_config():
    """Test validation with a valid configuration"""
    logger.info("Testing valid configuration...")

    # Create a valid environment file
    env_content = """
# Valid E2E configuration
ENVIRONMENT=e2e_testing
DEBUG_MODE=true
LOG_LEVEL=INFO
E2E_MODE=true
MOCKUP_ENABLED=true

# Database configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory  # pragma: allowlist secret

# API keys
OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456
GOOGLE_MAPS_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz
SENDGRID_API_KEY=SG.abcdefghijklmnopqrstuvwxyz123456789.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm

# Email configuration
EMAIL_FROM=test@example.com
EMAIL_OVERRIDE=developer@example.com

# Pipeline configuration
ENABLE_PIPELINE=true
MAX_WORKERS=4
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
"""

    env_file = create_test_env_file(env_content)

    try:
        # Create validator
        validator = ConfigValidator(env_file=env_file)

        # Run validation
        result = validator.validate()

        # Check result
        if result.success:
            logger.info("✅ Test passed: Valid configuration validated successfully")
        else:
            logger.error("❌ Test failed: Valid configuration reported as invalid")
            logger.error(f"Message: {result.message}")
            for issue in result.issues:
                logger.error(f"  - {issue}")
            return False

        return result.success
    finally:
        # Clean up
        os.unlink(env_file)


def test_missing_variables():
    """Test validation with missing required variables"""
    logger.info("Testing missing variables...")

    # Create an environment file with missing variables
    env_content = """
# Missing several required variables
ENVIRONMENT=e2e_testing
DEBUG_MODE=true

# Database configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory  # pragma: allowlist secret

# Email configuration
EMAIL_FROM=test@example.com
"""

    env_file = create_test_env_file(env_content)

    try:
        # Create validator
        validator = ConfigValidator(env_file=env_file)

        # Run validation
        result = validator.validate()

        # Check result
        if not result.success and len(result.issues) > 0:
            logger.info("✅ Test passed: Missing variables detected correctly")
        else:
            logger.error("❌ Test failed: Missing variables not detected")
            return False

        return not result.success
    finally:
        # Clean up
        os.unlink(env_file)


def test_invalid_formats():
    """Test validation with invalid variable formats"""
    logger.info("Testing invalid formats...")

    # Create an environment file with invalid formats
    env_content = """
# Valid core configuration
ENVIRONMENT=e2e_testing
DEBUG_MODE=true
LOG_LEVEL=INFO
E2E_MODE=true
MOCKUP_ENABLED=true

# Invalid database URL
DATABASE_URL=invalid-url

# Invalid email format
EMAIL_FROM=not-an-email

# Other required variables
OPENAI_API_KEY=invalid-key
GOOGLE_MAPS_API_KEY=invalid-key
SENDGRID_API_KEY=invalid-key
EMAIL_OVERRIDE=developer@example.com
ENABLE_PIPELINE=true
MAX_WORKERS=4
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
"""

    env_file = create_test_env_file(env_content)

    try:
        # Create validator
        validator = ConfigValidator(env_file=env_file)

        # Run validation
        result = validator.validate()

        # Check result
        if not result.success and len(result.issues) > 0:
            logger.info("✅ Test passed: Invalid formats detected correctly")
        else:
            logger.error("❌ Test failed: Invalid formats not detected")
            return False

        return not result.success
    finally:
        # Clean up
        os.unlink(env_file)


def test_mockup_mode():
    """Test validation in mockup mode (API keys not required)"""
    logger.info("Testing mockup mode...")

    # Create an environment file with mockup mode enabled and missing API keys
    env_content = """
# Valid core configuration with mockup mode
ENVIRONMENT=e2e_testing
DEBUG_MODE=true
LOG_LEVEL=INFO
E2E_MODE=true
MOCKUP_ENABLED=true

# Database configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory  # pragma: allowlist secret

# Only OpenAI API key (required even in mockup mode)
OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456

# Email configuration
EMAIL_FROM=test@example.com
EMAIL_OVERRIDE=developer@example.com

# Pipeline configuration
ENABLE_PIPELINE=true
MAX_WORKERS=4
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
"""

    env_file = create_test_env_file(env_content)

    try:
        # Create validator
        validator = ConfigValidator(env_file=env_file)

        # Run validation
        result = validator.validate()

        # Check result
        if result.success:
            logger.info("✅ Test passed: Mockup mode validation successful")
        else:
            logger.error("❌ Test failed: Mockup mode validation failed")
            logger.error(f"Message: {result.message}")
            for issue in result.issues:
                logger.error(f"  - {issue}")
            return False

        return result.success
    finally:
        # Clean up
        os.unlink(env_file)


def test_generate_sample():
    """Test generation of sample environment file"""
    logger.info("Testing sample generation...")

    output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".env.sample").name

    try:
        # Create validator
        validator = ConfigValidator()

        # Generate sample file
        success = validator.generate_sample_env(output_file=output_file)

        # Check if file was created
        if success and os.path.exists(output_file):
            with open(output_file) as f:
                content = f.read()

            # Check if file contains all required variables
            for _category, vars_list in validator.REQUIRED_VARS.items():
                for var in vars_list:
                    if var not in content:
                        logger.error(f"❌ Test failed: {var} missing from sample file")
                        return False

            logger.info(
                "✅ Test passed: Sample environment file generated successfully"
            )
            return True
        else:
            logger.error("❌ Test failed: Sample environment file not generated")
            return False
    finally:
        # Clean up
        if os.path.exists(output_file):
            os.unlink(output_file)


def main():
    """Run all tests"""
    tests = [
        ("Valid configuration", test_valid_config),
        ("Missing variables", test_missing_variables),
        ("Invalid formats", test_invalid_formats),
        ("Mockup mode", test_mockup_mode),
        ("Generate sample", test_generate_sample),
    ]

    test_results = []

    for test_name, test_func in tests:

        try:
            result = test_func()
            test_results.append((test_name, result))

            if result:
                pass
            else:
                pass
        except Exception:
            test_results.append((test_name, False))

    # Print summary

    passed = sum(1 for _, result in test_results if result)
    failed = len(test_results) - passed

    for test_name, result in test_results:
        pass

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
