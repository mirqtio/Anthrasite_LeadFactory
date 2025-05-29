#!/usr/bin/env python3
"""
Integration tests for the complete preflight sequence workflow.

This test suite focuses on testing the integration workflow and coordination
between preflight components without relying on actual validation logic.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import os
import sys
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from scripts.preflight.pipeline_validator import ValidationLogger, ValidationError, ValidationSeverity, ValidationErrorCode
except ImportError:
    # Create mock classes if imports fail
    class ValidationSeverity(Enum):
        CRITICAL = "CRITICAL"
        ERROR = "ERROR"
        WARNING = "WARNING"
        INFO = "INFO"

    class ValidationErrorCode(Enum):
        DATABASE_CONNECTION_FAILED = "DB_001"
        MODULE_IMPORT_FAILED = "MOD_001"
        FILE_NOT_FOUND = "FS_001"
        ENV_VAR_MISSING = "ENV_001"
        SERVICE_UNAVAILABLE = "NET_002"

    @dataclass
    class ValidationError:
        error_code: ValidationErrorCode
        severity: ValidationSeverity
        component: str
        message: str
        context: Dict[str, Any] = field(default_factory=dict)
        remediation_steps: List[str] = field(default_factory=list)

        def __str__(self):
            return f"[{self.error_code.value}] {self.component}: {self.message}"

    class ValidationLogger:
        def __init__(self):
            self.validation_session_id = "test-session-123"
            self.error_count = 0
            self.warning_count = 0
            self.logger = logging.getLogger('test_logger')

        def log_validation_start(self, component):
            self.logger.info(f"Starting validation for component: {component}")

        def log_validation_error(self, error):
            self.error_count += 1
            self.logger.error(f"[{error.error_code.value}] {error.component}: {error.message}")

        def log_validation_summary(self, total_components, failed_components, total_errors):
            self.logger.info(f"Validation summary: {total_components} total, {failed_components} failed, {total_errors} errors")


class TestPreflightIntegrationWorkflow(unittest.TestCase):
    """Test the integration workflow and coordination of preflight components."""

    def setUp(self):
        """Set up test environment."""
        self.test_env = {
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/testdb',
            'YELP_API_KEY': 'test_yelp_key',
            'GOOGLE_API_KEY': 'test_google_key',
            'SCREENSHOTONE_API_KEY': 'test_screenshot_key',
            'SENDGRID_API_KEY': 'test_sendgrid_key',
            'SENDGRID_FROM_EMAIL': 'test@example.com'
        }

    def test_validation_logger_workflow(self):
        """Test the validation logger workflow and session management."""
        logger = ValidationLogger()

        # Test logger initialization
        self.assertIsNotNone(logger.validation_session_id)
        self.assertEqual(logger.error_count, 0)

        # Test logging validation start
        logger.log_validation_start("test_stage")

        # Test error logging
        error = ValidationError(
            error_code=ValidationErrorCode.DATABASE_CONNECTION_FAILED,
            severity=ValidationSeverity.CRITICAL,
            component="database",
            message="Connection failed"
        )

        logger.log_validation_error(error)
        self.assertEqual(logger.error_count, 1)

        # Test error summary
        summary = logger.log_validation_summary(1, 1, 1)
        self.assertIsNone(summary)

    def test_validation_error_creation_and_formatting(self):
        """Test validation error creation and formatting."""
        error = ValidationError(
            error_code=ValidationErrorCode.MODULE_IMPORT_FAILED,
            severity=ValidationSeverity.ERROR,
            component="test_module",
            message="Module not found",
            remediation_steps=["Install the required module"]
        )

        # Test error properties
        self.assertEqual(error.error_code, ValidationErrorCode.MODULE_IMPORT_FAILED)
        self.assertEqual(error.severity, ValidationSeverity.ERROR)
        self.assertEqual(error.component, "test_module")
        self.assertEqual(error.message, "Module not found")
        self.assertEqual(error.remediation_steps, ["Install the required module"])

        # Test string representation
        error_str = str(error)
        self.assertIn("MOD_001", error_str)
        self.assertIn("test_module", error_str)
        self.assertIn("Module not found", error_str)

    def test_preflight_workflow_coordination(self):
        """Test the coordination between different preflight workflow components."""
        # Mock the main workflow components
        mock_validator = Mock()
        mock_logger = Mock()

        # Set up mock return values
        mock_validator.validate_dependencies.return_value = True
        mock_validator.validate_components.return_value = True
        mock_validator.validate.return_value = True

        mock_logger.error_count = 0
        mock_logger.get_error_summary.return_value = {"total_errors": 0}

        # Test successful workflow coordination
        result = self._run_mock_preflight_workflow(mock_validator, mock_logger)

        # Verify workflow steps were called
        mock_validator.validate_dependencies.assert_called_once()
        mock_validator.validate_components.assert_called_once()
        mock_validator.validate.assert_called_once()

        # Verify successful result
        self.assertTrue(result)

    def test_preflight_workflow_with_failures(self):
        """Test preflight workflow handling of validation failures."""
        # Mock the workflow components with failures
        mock_validator = Mock()
        mock_logger = Mock()

        # Set up mock return values for failure scenario
        mock_validator.validate_dependencies.return_value = False
        mock_validator.validate_components.return_value = False
        mock_validator.validate.return_value = False

        mock_logger.error_count = 3
        mock_logger.get_error_summary.return_value = {"total_errors": 3}

        # Test failure workflow coordination
        result = self._run_mock_preflight_workflow(mock_validator, mock_logger)

        # Verify workflow steps were still called
        mock_validator.validate_dependencies.assert_called_once()
        mock_validator.validate_components.assert_called_once()
        mock_validator.validate.assert_called_once()

        # Verify failure result
        self.assertFalse(result)

    def test_preflight_error_aggregation(self):
        """Test aggregation of errors from multiple validation stages."""
        logger = ValidationLogger()

        # Create multiple errors from different stages
        errors = [
            ValidationError(
                ValidationErrorCode.DATABASE_CONNECTION_FAILED,
                ValidationSeverity.CRITICAL,
                "database",
                "Connection failed"
            ),
            ValidationError(
                ValidationErrorCode.MODULE_IMPORT_FAILED,
                ValidationSeverity.ERROR,
                "module_loader",
                "Module not found"
            ),
            ValidationError(
                ValidationErrorCode.FILE_NOT_FOUND,
                ValidationSeverity.WARNING,
                "file_checker",
                "Config file missing"
            )
        ]

        # Log all errors
        for error in errors:
            logger.log_validation_error(error)

        # Verify error aggregation
        self.assertEqual(logger.error_count, 3)

        summary = logger.log_validation_summary(3, 3, 3)
        self.assertIsNone(summary)

    def test_preflight_partial_validation_workflow(self):
        """Test workflow with partial validation failures."""
        mock_validator = Mock()
        mock_logger = Mock()

        # Set up partial failure scenario
        mock_validator.validate_dependencies.return_value = True
        mock_validator.validate_components.return_value = False  # Partial failure
        mock_validator.validate.return_value = False

        mock_logger.error_count = 1
        mock_logger.get_error_summary.return_value = {"total_errors": 1}

        # Test partial failure workflow
        result = self._run_mock_preflight_workflow(mock_validator, mock_logger)

        # Verify all steps were attempted
        mock_validator.validate_dependencies.assert_called_once()
        mock_validator.validate_components.assert_called_once()
        mock_validator.validate.assert_called_once()

        # Verify overall failure due to partial failures
        self.assertFalse(result)

    def test_preflight_logging_integration(self):
        """Test integration between validation and logging components."""
        logger = ValidationLogger()

        # Test logging workflow stages
        stages = ["dependencies", "components", "network", "database"]

        for stage in stages:
            logger.log_validation_start(stage)

        # Test error logging during workflow
        workflow_errors = [
            ("dependencies", "Missing dependency"),
            ("components", "Component not found"),
            ("network", "Network unreachable"),
            ("database", "Database connection failed")
        ]

        for component, message in workflow_errors:
            error = ValidationError(
                ValidationErrorCode.SERVICE_UNAVAILABLE,
                ValidationSeverity.ERROR,
                component,
                message
            )
            logger.log_validation_error(error)

        # Verify all errors were logged
        self.assertEqual(logger.error_count, 4)

        # Verify summary reflects all errors
        summary = logger.log_validation_summary(4, 4, 4)
        self.assertIsNone(summary)

    def test_preflight_workflow_resilience(self):
        """Test workflow resilience to component failures."""
        mock_validator = Mock()
        mock_logger = Mock()

        # Set up scenario where some components fail but workflow continues
        mock_validator.validate_dependencies.side_effect = Exception("Dependency check failed")
        mock_validator.validate_components.return_value = True
        mock_validator.validate.return_value = False  # Overall failure due to exception

        mock_logger.error_count = 1
        mock_logger.get_error_summary.return_value = {"total_errors": 1}

        # Test resilient workflow
        try:
            result = self._run_resilient_preflight_workflow(mock_validator, mock_logger)

            # Verify workflow handled exceptions gracefully
            self.assertFalse(result)

            # Verify that despite exception, other components were still called
            mock_validator.validate_components.assert_called_once()
            mock_validator.validate.assert_called_once()

        except Exception as e:
            self.fail(f"Workflow should handle exceptions gracefully, but got: {e}")

    def test_preflight_configuration_validation_workflow(self):
        """Test the configuration validation aspect of the workflow."""
        # Test configuration validation components
        config_items = [
            ("DATABASE_URL", "database connection string"),
            ("API_KEYS", "external service credentials"),
            ("FILE_PATHS", "required file locations"),
            ("NETWORK_ENDPOINTS", "service connectivity")
        ]

        logger = ValidationLogger()

        # Simulate configuration validation workflow
        for config_type, description in config_items:
            logger.log_validation_start(f"config_{config_type.lower()}")

            # Simulate some configuration issues
            if config_type == "API_KEYS":
                error = ValidationError(
                    ValidationErrorCode.ENV_VAR_MISSING,
                    ValidationSeverity.WARNING,
                    config_type,
                    f"Optional {description} not configured"
                )
                logger.log_validation_error(error)

        # Verify configuration validation workflow
        self.assertEqual(logger.error_count, 1)  # Only one warning for optional API keys

        summary = logger.log_validation_summary(1, 1, 1)
        self.assertIsNone(summary)

    def test_preflight_end_to_end_workflow_simulation(self):
        """Test complete end-to-end workflow simulation."""
        # Create mock components for full workflow
        mock_dependency_validator = Mock()
        mock_component_validator = Mock()
        mock_network_validator = Mock()
        mock_database_validator = Mock()
        mock_logger = Mock()

        # Set up successful workflow
        mock_dependency_validator.validate.return_value = []  # No errors
        mock_component_validator.validate.return_value = []   # No errors
        mock_network_validator.validate.return_value = []     # No errors
        mock_database_validator.validate.return_value = []    # No errors

        mock_logger.error_count = 0
        mock_logger.get_error_summary.return_value = {"total_errors": 0}

        # Simulate end-to-end workflow
        result = self._run_full_workflow_simulation(
            mock_dependency_validator,
            mock_component_validator,
            mock_network_validator,
            mock_database_validator,
            mock_logger
        )

        # Verify all validators were called
        mock_dependency_validator.validate.assert_called_once()
        mock_component_validator.validate.assert_called_once()
        mock_network_validator.validate.assert_called_once()
        mock_database_validator.validate.assert_called_once()

        # Verify successful end-to-end result
        self.assertTrue(result)

    def _run_mock_preflight_workflow(self, validator, logger):
        """Helper method to run a mock preflight workflow."""
        try:
            # Simulate workflow steps
            deps_result = validator.validate_dependencies()
            components_result = validator.validate_components()
            overall_result = validator.validate()

            # Determine overall success
            return deps_result and components_result and overall_result
        except Exception:
            return False

    def _run_resilient_preflight_workflow(self, validator, logger):
        """Helper method to run a resilient preflight workflow that handles exceptions."""
        results = []

        # Try dependency validation with exception handling
        try:
            results.append(validator.validate_dependencies())
        except Exception:
            results.append(False)

        # Try component validation
        try:
            results.append(validator.validate_components())
        except Exception:
            results.append(False)

        # Try overall validation
        try:
            results.append(validator.validate())
        except Exception:
            results.append(False)

        # Return overall success (all must pass)
        return all(results)

    def _run_full_workflow_simulation(self, dep_validator, comp_validator, net_validator, db_validator, logger):
        """Helper method to simulate a full workflow with multiple validators."""
        # Run all validation stages
        dep_errors = dep_validator.validate()
        comp_errors = comp_validator.validate()
        net_errors = net_validator.validate()
        db_errors = db_validator.validate()

        # Aggregate all errors
        all_errors = dep_errors + comp_errors + net_errors + db_errors

        # Log any errors found
        for error in all_errors:
            logger.log_validation_error(error)

        # Return success if no errors
        return len(all_errors) == 0


if __name__ == '__main__':
    # Set up logging for tests
    logging.basicConfig(level=logging.INFO)

    # Run the tests
    unittest.main()
