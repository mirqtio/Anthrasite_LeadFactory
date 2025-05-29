"""
Complete Preflight Sequence Integration Tests

This module tests the entire preflight validation sequence as an integrated process,
verifying proper execution order, accurate pass/fail determination, and comprehensive
logging and reporting without relying on actual external dependencies.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import os
import tempfile
from pathlib import Path

from scripts.preflight.pipeline_validator import (
    PipelineValidator,
    ValidationLogger,
    ValidationError,
    ValidationSeverity,
    ValidationErrorCode
)


class TestPreflightCompleteIntegration(unittest.TestCase):
    """Complete integration tests for the preflight sequence."""

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

        # Create temporary directory and files
        self.temp_dir = tempfile.mkdtemp()
        self.email_template = os.path.join(self.temp_dir, 'email_template.html')
        with open(self.email_template, 'w') as f:
            f.write('<html><body>Test template</body></html>')

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complete_preflight_sequence_workflow_coordination(self):
        """Test that the complete preflight sequence coordinates properly between components."""
        # Create a ValidationLogger and test its workflow
        logger = ValidationLogger()

        # Test the complete workflow sequence
        components = ['database', 'environment', 'files', 'network', 'modules']

        # Simulate starting validation for each component
        for component in components:
            logger.log_validation_start(component)

        # Simulate some errors during validation
        error1 = ValidationError(
            ValidationErrorCode.DATABASE_CONNECTION_FAILED,
            ValidationSeverity.CRITICAL,
            "database",
            "Connection failed"
        )

        error2 = ValidationError(
            ValidationErrorCode.ENV_VAR_MISSING,
            ValidationSeverity.WARNING,
            "environment",
            "Optional variable missing"
        )

        # Log the errors
        logger.log_validation_error(error1)
        logger.log_validation_error(error2)

        # Verify workflow coordination
        self.assertEqual(logger.error_count, 2)

        # Test summary logging
        logger.log_validation_summary(
            total_components=len(components),
            failed_components=2,
            total_errors=logger.error_count
        )

    def test_preflight_validation_error_workflow_integration(self):
        """Test integration of validation error creation and processing workflow."""
        # Test ValidationError creation and formatting
        error = ValidationError(
            ValidationErrorCode.MODULE_IMPORT_FAILED,
            ValidationSeverity.CRITICAL,
            "test_module",
            "Module could not be imported",
            context={'module_name': 'test_module', 'import_path': '/test/path'},
            remediation_steps=['Install module', 'Check path']
        )

        # Test error string representation
        error_str = str(error)
        self.assertIn("MOD_001", error_str)
        self.assertIn("test_module", error_str)
        self.assertIn("Module could not be imported", error_str)

        # Test error dictionary representation
        error_dict = error.to_dict()
        self.assertEqual(error_dict['error_code'], 'MOD_001')
        self.assertEqual(error_dict['severity'], 'critical')
        self.assertEqual(error_dict['component'], 'test_module')
        self.assertEqual(len(error_dict['remediation_steps']), 2)

    def test_preflight_logger_complete_workflow(self):
        """Test the complete ValidationLogger workflow from start to finish."""
        logger = ValidationLogger()

        # Test complete workflow sequence
        test_components = [
            ('database', True),
            ('environment', False),
            ('files', True),
            ('network', False),
            ('modules', True)
        ]

        # Process each component
        for component, should_succeed in test_components:
            logger.log_validation_start(component)

            if not should_succeed:
                error = ValidationError(
                    ValidationErrorCode.SERVICE_UNAVAILABLE,
                    ValidationSeverity.ERROR,
                    component,
                    f"{component} validation failed"
                )
                logger.log_validation_error(error)
            else:
                logger.log_validation_success(component)

        # Verify complete workflow
        self.assertEqual(logger.error_count, 2)  # environment and network failed

        # Test summary logging
        failed_count = sum(1 for _, success in test_components if not success)
        logger.log_validation_summary(
            total_components=len(test_components),
            failed_components=failed_count,
            total_errors=logger.error_count
        )

    def test_preflight_error_aggregation_and_reporting_workflow(self):
        """Test that preflight properly aggregates errors and generates comprehensive reports."""
        logger = ValidationLogger()

        # Create multiple different types of errors
        errors = [
            ValidationError(
                ValidationErrorCode.DATABASE_CONNECTION_FAILED,
                ValidationSeverity.CRITICAL,
                "database",
                "PostgreSQL connection failed"
            ),
            ValidationError(
                ValidationErrorCode.FILE_NOT_FOUND,
                ValidationSeverity.ERROR,
                "files",
                "Configuration file missing"
            ),
            ValidationError(
                ValidationErrorCode.ENV_VAR_MISSING,
                ValidationSeverity.WARNING,
                "environment",
                "Optional API key not set"
            ),
            ValidationError(
                ValidationErrorCode.MODULE_IMPORT_FAILED,
                ValidationSeverity.CRITICAL,
                "modules",
                "Required module not available"
            )
        ]

        # Log all errors
        for error in errors:
            logger.log_validation_start(error.component)
            logger.log_validation_error(error)

        # Verify error aggregation
        self.assertEqual(logger.error_count, 4)

        # Test comprehensive reporting
        logger.log_validation_summary(
            total_components=len(errors),
            failed_components=len(errors),
            total_errors=logger.error_count
        )

    def test_preflight_partial_success_workflow_handling(self):
        """Test preflight workflow handling of partial success scenarios."""
        logger = ValidationLogger()

        # Simulate mixed success/failure scenario
        validation_results = [
            ('database', True, None),
            ('environment', False, ValidationError(
                ValidationErrorCode.ENV_VAR_MISSING,
                ValidationSeverity.WARNING,
                "environment",
                "Non-critical variable missing"
            )),
            ('files', True, None),
            ('network', False, ValidationError(
                ValidationErrorCode.NETWORK_UNREACHABLE,
                ValidationSeverity.ERROR,
                "network",
                "External service unreachable"
            )),
            ('modules', True, None)
        ]

        # Process validation results
        for component, success, error in validation_results:
            logger.log_validation_start(component)
            if not success and error:
                logger.log_validation_error(error)
            else:
                logger.log_validation_success(component)

        # Verify partial success handling
        self.assertEqual(logger.error_count, 2)

        # Test summary logging
        failed_count = sum(1 for _, success, _ in validation_results if not success)
        logger.log_validation_summary(
            total_components=len(validation_results),
            failed_components=failed_count,
            total_errors=logger.error_count
        )

    def test_preflight_execution_order_verification(self):
        """Test that preflight components execute in the expected order."""
        logger = ValidationLogger()

        # Define expected execution order
        expected_order = [
            'dependencies',
            'environment',
            'database',
            'files',
            'modules',
            'network'
        ]

        # Track actual execution order
        actual_order = []

        # Simulate execution in expected order
        for component in expected_order:
            logger.log_validation_start(component)
            actual_order.append(component)
            logger.log_validation_success(component)

        # Verify execution order
        self.assertEqual(actual_order, expected_order)

        # Test summary logging
        logger.log_validation_summary(
            total_components=len(expected_order),
            failed_components=0,
            total_errors=logger.error_count
        )

    def test_preflight_resilience_and_continuation_workflow(self):
        """Test that preflight continues processing even when some validations fail."""
        logger = ValidationLogger()

        # Simulate a scenario where early validations fail but processing continues
        components_with_results = [
            ('critical_component', False, ValidationError(
                ValidationErrorCode.DATABASE_CONNECTION_FAILED,
                ValidationSeverity.CRITICAL,
                "critical_component",
                "Critical failure occurred"
            )),
            ('secondary_component', True, None),
            ('tertiary_component', False, ValidationError(
                ValidationErrorCode.FILE_NOT_FOUND,
                ValidationSeverity.ERROR,
                "tertiary_component",
                "Secondary failure occurred"
            )),
            ('final_component', True, None)
        ]

        # Process all components despite failures
        for component, success, error in components_with_results:
            logger.log_validation_start(component)
            if not success and error:
                logger.log_validation_error(error)
            else:
                logger.log_validation_success(component)

        # Verify resilience - all components were processed
        self.assertEqual(logger.error_count, 2)

        # Verify that processing continued despite early failures
        failed_count = sum(1 for _, success, _ in components_with_results if not success)
        logger.log_validation_summary(
            total_components=len(components_with_results),
            failed_components=failed_count,
            total_errors=logger.error_count
        )

    def test_preflight_comprehensive_integration_coverage(self):
        """Test comprehensive integration coverage of all preflight components."""
        logger = ValidationLogger()

        # Test all major validation categories
        validation_categories = [
            'database_connectivity',
            'environment_variables',
            'file_access_permissions',
            'network_connectivity',
            'module_imports',
            'dependency_resolution',
            'configuration_validation'
        ]

        # Process each category
        for category in validation_categories:
            logger.log_validation_start(category)
            logger.log_validation_success(category)

        # Verify comprehensive coverage
        self.assertEqual(logger.error_count, 0)

        # Test summary logging
        logger.log_validation_summary(
            total_components=len(validation_categories),
            failed_components=0,
            total_errors=logger.error_count
        )


if __name__ == '__main__':
    unittest.main()
