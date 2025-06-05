"""
Integration tests for preflight validation scenarios.

This module tests complex validation scenarios that involve multiple checks
working together, edge cases, and real-world failure conditions.
"""

import os

# Add the project root to the path
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.preflight.pipeline_validator import (
    DatabaseConnectionRule,
    EnvironmentVariableRule,
    FileAccessRule,
    ModuleImportRule,
    NetworkConnectivityRule,
    PipelineValidator,
    ValidationError,
    ValidationErrorCode,
    ValidationLogger,
    ValidationSeverity,
)


class TestPipelineValidatorIntegration:
    """Test PipelineValidator with multiple validation scenarios."""

    def test_validate_with_all_dependencies_satisfied(self):
        """Test validating when all dependencies are satisfied."""
        validator = PipelineValidator()

        # Mock environment variables for all stages
        env_vars = {
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "YELP_API_KEY": "test_yelp_key",
            "GOOGLE_API_KEY": "test_google_key",
            "SCREENSHOTONE_API_KEY": "test_screenshot_key",
            "SENDGRID_API_KEY": "test_sendgrid_key",
            "SENDGRID_FROM_EMAIL": "test@example.com",
        }

        with patch.dict(os.environ, env_vars):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                with patch("os.access", return_value=True):  # Mock file access
                    result = validator.validate()

        # Should have minimal issues when all dependencies are satisfied
        critical_issues = [
            issue
            for issue in result.issues
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        assert len(critical_issues) == 0

    def test_validate_with_missing_database(self):
        """Test validating when database connection fails."""
        validator = PipelineValidator()

        # Missing DATABASE_URL
        env_vars = {
            "YELP_API_KEY": "test_yelp_key",
            "GOOGLE_API_KEY": "test_google_key",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            result = validator.validate()

        # Should have database-related issues
        database_issues = [
            issue for issue in result.issues if "DATABASE_URL" in issue.message
        ]
        assert len(database_issues) > 0

    def test_validate_with_missing_api_keys(self):
        """Test validating when API keys are missing."""
        validator = PipelineValidator()

        # Missing API keys
        env_vars = {"DATABASE_URL": "postgresql://test:test@localhost/test"}

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                result = validator.validate()

        # Should have API key related issues
        api_key_issues = [
            issue for issue in result.issues if "API_KEY" in issue.message
        ]
        assert len(api_key_issues) > 0

    def test_validate_component_with_mixed_results(self):
        """Test validating components with some passing and some failing."""
        validator = PipelineValidator()

        # Partial environment setup - database works but missing some API keys
        env_vars = {
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "YELP_API_KEY": "test_yelp_key",
            # Missing GOOGLE_API_KEY and others
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                result = validator.validate()

        # Should have some issues but not complete failure
        assert len(result.issues) > 0

        # Check that we have specific API key issues
        google_api_issues = [
            issue for issue in result.issues if "GOOGLE_API_KEY" in issue.message
        ]
        assert len(google_api_issues) > 0

    def test_validate_with_file_dependencies(self):
        """Test validating when file access is required."""
        validator = PipelineValidator()

        # Create temporary files for testing
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as email_template:
            email_template.write("<html><body>Test template</body></html>")
            email_template_path = email_template.name

        try:
            env_vars = {
                "DATABASE_URL": "postgresql://test:test@localhost/test",
                "YELP_API_KEY": "test_yelp_key",
                "GOOGLE_API_KEY": "test_google_key",
            }

            with patch.dict(os.environ, env_vars):
                with patch("psycopg2.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_connect.return_value = mock_conn

                    with patch("os.access", return_value=True):  # Mock file access
                        result = validator.validate()

            # Should have minimal critical issues when files exist
            critical_issues = [
                issue
                for issue in result.issues
                if issue.severity == ValidationSeverity.CRITICAL
            ]
            assert len(critical_issues) == 0
        finally:
            os.unlink(email_template_path)

    def test_validate_with_missing_files(self):
        """Test validating when required files are missing."""
        validator = PipelineValidator()

        env_vars = {
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "YELP_API_KEY": "test_yelp_key",
            "GOOGLE_API_KEY": "test_google_key",
        }

        with patch.dict(os.environ, env_vars):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                # Don't mock file access - let it fail naturally
                result = validator.validate()

        # Should have file-related issues
        file_issues = [
            issue
            for issue in result.issues
            if issue.error_code == ValidationErrorCode.FILE_NOT_FOUND
        ]
        assert len(file_issues) > 0

    def test_validate_dependencies_circular_detection(self):
        """Test detection of circular dependencies."""
        validator = PipelineValidator()

        # Mock circular dependencies
        circular_deps = {
            "stage1": ["stage2"],
            "stage2": ["stage3"],
            "stage3": ["stage1"],  # Creates a cycle
        }

        with patch.object(validator, "STAGE_DEPENDENCIES", circular_deps):
            issues = validator.validate_dependencies(["stage1", "stage2", "stage3"])

        # Should detect circular dependency
        circular_issues = [
            issue
            for issue in issues
            if issue.error_code == ValidationErrorCode.DEPENDENCY_CIRCULAR
        ]
        assert len(circular_issues) > 0

    def test_validate_dependencies_missing_stages(self):
        """Test validation when referenced stages don't exist."""
        validator = PipelineValidator()

        # Mock dependencies that reference non-existent stages
        mock_deps = {"existing_stage": ["missing_stage"]}

        with patch.object(validator, "STAGE_DEPENDENCIES", mock_deps):
            issues = validator.validate_dependencies(["existing_stage"])

        # Should detect missing dependency
        missing_issues = [
            issue
            for issue in issues
            if issue.error_code == ValidationErrorCode.DEPENDENCY_MISSING
        ]
        assert len(missing_issues) > 0

    def test_validate_all_comprehensive(self):
        """Test comprehensive validation of all pipeline components."""
        validator = PipelineValidator()

        # Set up comprehensive environment
        env_vars = {
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "YELP_API_KEY": "test_yelp_key",
            "GOOGLE_API_KEY": "test_google_key",
            "SCREENSHOTONE_API_KEY": "test_screenshot_key",
            "SENDGRID_API_KEY": "test_sendgrid_key",
            "SENDGRID_FROM_EMAIL": "test@example.com",
        }

        with patch.dict(os.environ, env_vars):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                with patch("os.access", return_value=True):  # Mock file access
                    result = validator.validate()

        # With all environment variables set and mocked file access,
        # there should be minimal critical issues
        critical_issues = [
            issue
            for issue in result.issues
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        assert len(critical_issues) == 0  # No critical issues


class TestValidationLoggerIntegration:
    """Test ValidationLogger integration with validation processes."""

    def test_validation_logger_error_tracking(self):
        """Test that ValidationLogger properly tracks and logs errors."""
        logger = ValidationLogger("test_logger")

        # Create test validation errors
        error1 = ValidationError(
            error_code=ValidationErrorCode.ENV_VAR_MISSING,
            severity=ValidationSeverity.ERROR,
            component="test_component",
            message="Test error message",
        )

        error2 = ValidationError(
            error_code=ValidationErrorCode.DATABASE_CONNECTION_FAILED,
            severity=ValidationSeverity.CRITICAL,
            component="database",
            message="Database connection failed",
        )

        # Log errors
        logger.log_validation_error(error1)
        logger.log_validation_error(error2)

        # Check that error count is tracked
        assert logger.error_count == 2

    def test_validation_logger_summary_generation(self):
        """Test that ValidationLogger generates proper summaries."""
        logger = ValidationLogger("test_logger")

        # Test summary generation
        logger.log_validation_summary(
            total_components=5, failed_components=2, total_errors=3
        )

        # Should complete without errors
        assert logger.validation_session_id is not None
        assert len(logger.validation_session_id) == 8

    def test_validation_logger_component_tracking(self):
        """Test that ValidationLogger tracks component validation lifecycle."""
        logger = ValidationLogger("test_logger")

        # Test component lifecycle
        logger.log_validation_start("test_component")
        logger.log_validation_success("test_component")

        # Should complete without errors
        assert logger.validation_session_id is not None


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""

    def test_validation_with_empty_environment(self):
        """Test validation with completely empty environment."""
        validator = PipelineValidator()

        with patch.dict(os.environ, {}, clear=True):
            result = validator.validate()

        # Should have multiple environment variable issues
        env_issues = [
            issue
            for issue in result.issues
            if issue.error_code == ValidationErrorCode.ENV_VAR_MISSING
        ]
        assert len(env_issues) > 0

    def test_validation_with_malformed_database_url(self):
        """Test validation with malformed database URL."""
        validator = PipelineValidator()

        env_vars = {
            "DATABASE_URL": "not-a-valid-url",
            "YELP_API_KEY": "test_key",
            "GOOGLE_API_KEY": "test_key",
        }

        with patch.dict(os.environ, env_vars), patch(
            "psycopg2.connect", side_effect=Exception("Invalid connection string")
        ):
            result = validator.validate()

        # Should have database connection issues
        db_issues = [
            issue
            for issue in result.issues
            if issue.error_code == ValidationErrorCode.DATABASE_CONNECTION_FAILED
        ]
        assert len(db_issues) > 0

    def test_validation_with_network_timeout(self):
        """Test validation behavior when network requests timeout."""
        # Create a rule that will timeout
        rule = NetworkConnectivityRule("http://httpbin.org/delay/10", timeout=1)

        issues = rule.validate({})

        # Should have network connectivity issues
        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.SERVICE_UNAVAILABLE

    def test_validation_with_permission_errors(self):
        """Test file validation with permission errors."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            rule = FileAccessRule(tmp_path, "write")

            # Mock permission denied
            with patch("os.access", return_value=False):
                issues = rule.validate({})

            assert len(issues) == 1
            assert issues[0].error_code == ValidationErrorCode.FILE_NOT_FOUND
        finally:
            os.unlink(tmp_path)

    def test_validation_with_unicode_paths(self):
        """Test file validation with unicode characters in paths."""
        unicode_path = "/tmp/测试文件.txt"
        rule = FileAccessRule(unicode_path, "read")

        issues = rule.validate({})

        # Should handle unicode paths gracefully
        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.FILE_NOT_FOUND
        assert unicode_path in issues[0].message

    def test_validation_with_very_long_paths(self):
        """Test file validation with very long file paths."""
        # Use a more reasonable long path that won't cause OS errors
        long_path = "/tmp/" + "a" * 200 + ".txt"
        rule = FileAccessRule(long_path, "read")

        issues = rule.validate({})

        # Should handle long paths gracefully
        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.FILE_NOT_FOUND

    def test_validation_with_special_characters_in_env_vars(self):
        """Test environment variable validation with special characters."""
        rule = EnvironmentVariableRule("TEST_VAR_WITH_SPECIAL_CHARS", required=True)

        # Test with various special characters
        special_values = [
            "value with spaces",
            "value@with#special$chars%",
            "value\nwith\nnewlines",
            "value\twith\ttabs",
            "value\"with'quotes",
            "value\\with\\backslashes",
        ]

        for value in special_values:
            with patch.dict(os.environ, {"TEST_VAR_WITH_SPECIAL_CHARS": value}):
                issues = rule.validate({})

                # Should accept any non-empty value
                assert len(issues) == 0

    def test_validation_error_serialization(self):
        """Test that validation errors can be properly serialized."""
        error = ValidationError(
            error_code=ValidationErrorCode.ENV_VAR_MISSING,
            severity=ValidationSeverity.ERROR,
            component="test_component",
            message="Test message with unicode: 测试",
            context={
                "unicode_key": "unicode_value_测试",
                "number": 42,
                "boolean": True,
            },
            remediation_steps=["Step with unicode: 修复步骤"],
        )

        # Test dictionary conversion
        error_dict = error.to_dict()
        assert isinstance(error_dict, dict)
        assert error_dict["message"] == "Test message with unicode: 测试"
        assert error_dict["context"]["unicode_key"] == "unicode_value_测试"

        # Test string representation
        error_str = str(error)
        assert isinstance(error_str, str)
        assert "测试" in error_str


class TestRealWorldScenarios:
    """Test real-world validation scenarios."""

    def test_development_environment_setup(self):
        """Test validation for a typical development environment setup."""
        validator = PipelineValidator()

        # Typical development environment
        dev_env = {
            "DATABASE_URL": "postgresql://localhost:5432/leadfactory_dev",
            "YELP_API_KEY": "dev_yelp_key_12345",
            "GOOGLE_API_KEY": "dev_google_key_67890",
            # Missing production keys like SENDGRID_API_KEY
        }

        with patch.dict(os.environ, dev_env, clear=True):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                # Test scrape stage (should work)
                result = validator.validate()

                # Check that we have specific API key issues
                sendgrid_issues = [
                    issue for issue in result.issues if "SENDGRID" in issue.message
                ]
                assert len(sendgrid_issues) > 0

    def test_production_environment_validation(self):
        """Test validation for production environment requirements."""
        validator = PipelineValidator()

        # Production environment with all required keys
        prod_env = {
            "DATABASE_URL": "postgresql://prod-user:secure-pass@prod-db:5432/leadfactory",
            "YELP_API_KEY": "prod_yelp_key_abcdef",
            "GOOGLE_API_KEY": "prod_google_key_ghijkl",
            "SCREENSHOTONE_API_KEY": "prod_screenshot_key_mnopqr",
            "SENDGRID_API_KEY": "prod_sendgrid_key_stuvwx",
            "SENDGRID_FROM_EMAIL": "noreply@company.com",
        }

        with patch.dict(os.environ, prod_env):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                with patch("os.access", return_value=True):  # Mock file access
                    result = validator.validate()

        # Production environment should have minimal issues
        critical_issues = [
            issue
            for issue in result.issues
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        assert len(critical_issues) == 0

    def test_partial_pipeline_validation(self):
        """Test validation of a subset of pipeline stages."""
        validator = PipelineValidator()

        # Set up environment for only scrape and dedupe stages
        env_vars = {
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "YELP_API_KEY": "test_yelp_key",
            "GOOGLE_API_KEY": "test_google_key",
        }

        with patch.dict(os.environ, env_vars):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn

                result = validator.validate()

        # Should have some issues for missing API keys but not critical failures
        # for the basic components that have their dependencies satisfied
        critical_issues = [
            issue
            for issue in result.issues
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        assert len(critical_issues) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
