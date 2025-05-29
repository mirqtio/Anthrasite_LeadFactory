"""
Comprehensive unit tests for individual preflight validation checks.

This module tests each individual preflight check in isolation to verify
they function correctly under various conditions including pass/fail scenarios.
"""

import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the project root to the path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.preflight.pipeline_validator import (
    DatabaseConnectionRule,
    ModuleImportRule,
    FileAccessRule,
    EnvironmentVariableRule,
    NetworkConnectivityRule,
    ValidationError,
    ValidationSeverity,
    ValidationErrorCode,
    ValidationErrorBuilder
)


class TestDatabaseConnectionRule:
    """Test DatabaseConnectionRule in isolation."""

    def test_database_connection_rule_missing_url(self):
        """Test database connection rule when DATABASE_URL is missing."""
        rule = DatabaseConnectionRule()

        with patch.dict(os.environ, {}, clear=True):
            issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.ENV_VAR_MISSING
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "DATABASE_URL" in issues[0].message
        assert "database" == issues[0].component

    @patch('psycopg2.connect')
    def test_database_connection_rule_success(self, mock_connect):
        """Test successful database connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        rule = DatabaseConnectionRule()

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            issues = rule.validate({})

        assert len(issues) == 0
        mock_connect.assert_called_once_with("postgresql://test:test@localhost/test")
        mock_conn.close.assert_called_once()

    @patch('psycopg2.connect')
    def test_database_connection_rule_connection_failed(self, mock_connect):
        """Test database connection failure."""
        mock_connect.side_effect = Exception("Connection refused")

        rule = DatabaseConnectionRule()

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.DATABASE_CONNECTION_FAILED
        assert issues[0].severity == ValidationSeverity.CRITICAL
        assert "Connection refused" in issues[0].message
        assert "database" == issues[0].component

    def test_database_connection_rule_psycopg2_not_installed(self):
        """Test when psycopg2 is not installed."""
        rule = DatabaseConnectionRule()

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'psycopg2'")):
                issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.MODULE_IMPORT_FAILED
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "psycopg2" in issues[0].message


class TestModuleImportRule:
    """Test ModuleImportRule in isolation."""

    def test_module_import_rule_valid_module(self):
        """Test importing a valid module."""
        rule = ModuleImportRule("os")
        issues = rule.validate({})

        assert len(issues) == 0

    def test_module_import_rule_invalid_module(self):
        """Test importing a non-existent module."""
        rule = ModuleImportRule("nonexistent_module_xyz_123")
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.MODULE_IMPORT_FAILED
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "nonexistent_module_xyz_123" in issues[0].message

    def test_module_import_rule_module_with_syntax_error(self):
        """Test importing a module with syntax errors."""
        # Create a temporary Python file with syntax error
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
            tmp.write("invalid python syntax $$$ @@@")
            tmp_path = tmp.name

        try:
            # Extract module name from path
            module_name = Path(tmp_path).stem

            # Add the directory to Python path temporarily
            tmp_dir = os.path.dirname(tmp_path)
            with patch('sys.path', [tmp_dir] + sys.path):
                rule = ModuleImportRule(module_name)
                issues = rule.validate({})

            assert len(issues) == 1
            assert issues[0].error_code == ValidationErrorCode.MODULE_IMPORT_FAILED
            assert issues[0].severity == ValidationSeverity.ERROR
            assert module_name in issues[0].message
        finally:
            os.unlink(tmp_path)

    def test_module_import_rule_complex_module_path(self):
        """Test importing a module with complex path."""
        rule = ModuleImportRule("json.decoder")
        issues = rule.validate({})

        assert len(issues) == 0


class TestFileAccessRule:
    """Test FileAccessRule in isolation."""

    def test_file_access_rule_existing_file_read(self):
        """Test read access to an existing file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            rule = FileAccessRule(tmp_path, "read")
            issues = rule.validate({})

            assert len(issues) == 0
        finally:
            os.unlink(tmp_path)

    def test_file_access_rule_missing_file(self):
        """Test access to a non-existent file."""
        rule = FileAccessRule("/nonexistent/path/file.txt", "read")
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.FILE_NOT_FOUND
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "/nonexistent/path/file.txt" in issues[0].message

    def test_file_access_rule_write_access(self):
        """Test write access to a file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            rule = FileAccessRule(tmp_path, "write")
            issues = rule.validate({})

            assert len(issues) == 0
        finally:
            os.unlink(tmp_path)

    def test_file_access_rule_directory_access(self):
        """Test access to a directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            rule = FileAccessRule(tmp_dir, "read")
            issues = rule.validate({})

            assert len(issues) == 0

    @patch('os.access')
    def test_file_access_rule_permission_denied_read(self, mock_access):
        """Test read access denied scenario."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            # Mock os.access to return False for read access
            mock_access.return_value = False

            rule = FileAccessRule(tmp_path, "read")
            issues = rule.validate({})

            assert len(issues) == 1
            assert issues[0].error_code == ValidationErrorCode.FILE_NOT_FOUND
            assert issues[0].severity == ValidationSeverity.ERROR
        finally:
            os.unlink(tmp_path)

    @patch('os.access')
    def test_file_access_rule_permission_denied_write(self, mock_access):
        """Test write access denied scenario."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            # Mock os.access to return False for write access
            mock_access.return_value = False

            rule = FileAccessRule(tmp_path, "write")
            issues = rule.validate({})

            assert len(issues) == 1
            assert issues[0].error_code == ValidationErrorCode.FILE_NOT_FOUND
            assert issues[0].severity == ValidationSeverity.ERROR
        finally:
            os.unlink(tmp_path)


class TestEnvironmentVariableRule:
    """Test EnvironmentVariableRule in isolation."""

    def test_environment_variable_rule_required_present(self):
        """Test required environment variable that is present."""
        rule = EnvironmentVariableRule("TEST_PRESENT_VAR", required=True)

        with patch.dict(os.environ, {"TEST_PRESENT_VAR": "test_value"}):
            issues = rule.validate({})

        assert len(issues) == 0

    def test_environment_variable_rule_required_missing(self):
        """Test required environment variable that is missing."""
        rule = EnvironmentVariableRule("TEST_MISSING_VAR", required=True)

        with patch.dict(os.environ, {}, clear=True):
            issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.ENV_VAR_MISSING
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "TEST_MISSING_VAR" in issues[0].message

    def test_environment_variable_rule_optional_missing(self):
        """Test optional environment variable that is missing."""
        rule = EnvironmentVariableRule("TEST_OPTIONAL_VAR", required=False)

        with patch.dict(os.environ, {}, clear=True):
            issues = rule.validate({})

        assert len(issues) == 0

    def test_environment_variable_rule_optional_present(self):
        """Test optional environment variable that is present."""
        rule = EnvironmentVariableRule("TEST_OPTIONAL_VAR", required=False)

        with patch.dict(os.environ, {"TEST_OPTIONAL_VAR": "test_value"}):
            issues = rule.validate({})

        assert len(issues) == 0

    def test_environment_variable_rule_empty_value_required(self):
        """Test required environment variable with empty value."""
        rule = EnvironmentVariableRule("TEST_EMPTY_VAR", required=True)

        with patch.dict(os.environ, {"TEST_EMPTY_VAR": ""}):
            issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.ENV_VAR_MISSING
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "TEST_EMPTY_VAR" in issues[0].message

    def test_environment_variable_rule_empty_value_optional(self):
        """Test optional environment variable with empty value."""
        rule = EnvironmentVariableRule("TEST_EMPTY_VAR", required=False)

        with patch.dict(os.environ, {"TEST_EMPTY_VAR": ""}):
            issues = rule.validate({})

        assert len(issues) == 0

    def test_environment_variable_rule_whitespace_value(self):
        """Test environment variable with whitespace value."""
        rule = EnvironmentVariableRule("TEST_WHITESPACE_VAR", required=True)

        with patch.dict(os.environ, {"TEST_WHITESPACE_VAR": "   "}):
            issues = rule.validate({})

        # Whitespace should be considered a valid value
        assert len(issues) == 0


class TestNetworkConnectivityRule:
    """Test NetworkConnectivityRule in isolation."""

    @patch('requests.get')
    def test_network_connectivity_rule_success(self, mock_get):
        """Test successful network connectivity."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        rule = NetworkConnectivityRule("http://example.com", timeout=5)
        issues = rule.validate({})

        assert len(issues) == 0
        mock_get.assert_called_once_with("http://example.com", timeout=5)

    @patch('requests.get')
    def test_network_connectivity_rule_http_error(self, mock_get):
        """Test network connectivity with HTTP error status."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        rule = NetworkConnectivityRule("http://example.com/notfound", timeout=5)
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.SERVICE_UNAVAILABLE
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "example.com" in issues[0].message

    @patch('requests.get')
    def test_network_connectivity_rule_connection_error(self, mock_get):
        """Test network connectivity with connection error."""
        mock_get.side_effect = ConnectionError("Connection failed")

        rule = NetworkConnectivityRule("http://unreachable.example.com", timeout=5)
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.SERVICE_UNAVAILABLE
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "unreachable.example.com" in issues[0].message

    @patch('requests.get')
    def test_network_connectivity_rule_timeout(self, mock_get):
        """Test network connectivity with timeout."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timed out")

        rule = NetworkConnectivityRule("http://slow.example.com", timeout=1)
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.SERVICE_UNAVAILABLE
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "slow.example.com" in issues[0].message

    @patch('requests.get')
    def test_network_connectivity_rule_custom_timeout(self, mock_get):
        """Test network connectivity with custom timeout value."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        rule = NetworkConnectivityRule("http://example.com", timeout=10)
        issues = rule.validate({})

        assert len(issues) == 0
        mock_get.assert_called_once_with("http://example.com", timeout=10)

    @patch('requests.get')
    def test_network_connectivity_rule_https_url(self, mock_get):
        """Test network connectivity with HTTPS URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        rule = NetworkConnectivityRule("https://secure.example.com", timeout=5)
        issues = rule.validate({})

        assert len(issues) == 0
        mock_get.assert_called_once_with("https://secure.example.com", timeout=5)

    @patch('requests.get')
    def test_network_connectivity_rule_redirect_success(self, mock_get):
        """Test network connectivity with redirect (3xx status)."""
        mock_response = MagicMock()
        mock_response.status_code = 301
        mock_get.return_value = mock_response

        rule = NetworkConnectivityRule("http://redirect.example.com", timeout=5)
        issues = rule.validate({})

        # 301 is not 200, so should be treated as failure
        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.SERVICE_UNAVAILABLE
        assert issues[0].severity == ValidationSeverity.ERROR


class TestValidationErrorBuilder:
    """Test ValidationErrorBuilder utility functions."""

    def test_env_var_missing_error(self):
        """Test creating environment variable missing error."""
        error = ValidationErrorBuilder.env_var_missing("test_component", "TEST_VAR")

        assert error.error_code == ValidationErrorCode.ENV_VAR_MISSING
        assert error.severity == ValidationSeverity.ERROR
        assert error.component == "test_component"
        assert "TEST_VAR" in error.message
        assert "variable" in error.context
        assert error.context["variable"] == "TEST_VAR"
        assert len(error.remediation_steps) > 0

    def test_api_key_missing_error(self):
        """Test creating API key missing error."""
        api_keys = ["YELP_API_KEY", "GOOGLE_API_KEY"]
        error = ValidationErrorBuilder.api_key_missing("scrape", api_keys)

        assert error.error_code == ValidationErrorCode.API_KEY_MISSING
        assert error.severity == ValidationSeverity.ERROR
        assert error.component == "scrape"
        assert "YELP_API_KEY" in error.message
        assert "GOOGLE_API_KEY" in error.message
        assert error.context["missing_keys"] == api_keys
        assert error.context["key_count"] == 2

    def test_database_connection_failed_error(self):
        """Test creating database connection failed error."""
        error = ValidationErrorBuilder.database_connection_failed("database", "Connection refused")

        assert error.error_code == ValidationErrorCode.DATABASE_CONNECTION_FAILED
        assert error.severity == ValidationSeverity.CRITICAL
        assert error.component == "database"
        assert "Connection refused" in error.message
        assert error.context["error"] == "Connection refused"

    def test_file_not_found_error(self):
        """Test creating file not found error."""
        file_path = "/missing/file.txt"
        error = ValidationErrorBuilder.file_not_found("component", file_path)

        assert error.error_code == ValidationErrorCode.FILE_NOT_FOUND
        assert error.severity == ValidationSeverity.ERROR
        assert error.component == "component"
        assert file_path in error.message
        assert error.context["file_path"] == file_path

    def test_module_import_failed_error(self):
        """Test creating module import failed error."""
        error = ValidationErrorBuilder.module_import_failed("component", "missing_module", "No module named 'missing_module'")

        assert error.error_code == ValidationErrorCode.MODULE_IMPORT_FAILED
        assert error.severity == ValidationSeverity.ERROR
        assert error.component == "component"
        assert "missing_module" in error.message
        assert "No module named 'missing_module'" in error.message
        assert error.context["module_path"] == "missing_module"

    def test_dependency_circular_error(self):
        """Test creating circular dependency error."""
        cycle = ["stage1", "stage2", "stage3"]
        error = ValidationErrorBuilder.dependency_circular("pipeline", cycle)

        assert error.error_code == ValidationErrorCode.DEPENDENCY_CIRCULAR
        assert error.severity == ValidationSeverity.CRITICAL
        assert error.component == "pipeline"
        assert "stage1" in error.message
        assert "stage2" in error.message
        assert "stage3" in error.message
        assert error.context["cycle"] == cycle
        assert error.context["cycle_length"] == 3

    def test_dependency_missing_error_with_deps(self):
        """Test creating missing dependency error with dependencies."""
        missing_deps = ["dep1", "dep2"]
        error = ValidationErrorBuilder.dependency_missing("component", missing_deps)

        assert error.error_code == ValidationErrorCode.DEPENDENCY_MISSING
        assert error.severity == ValidationSeverity.ERROR
        assert error.component == "component"
        assert "dep1" in error.message
        assert "dep2" in error.message
        assert error.context["missing_dependencies"] == missing_deps

    def test_dependency_missing_error_no_deps(self):
        """Test creating missing dependency error for missing stage."""
        error = ValidationErrorBuilder.dependency_missing("missing_stage", [])

        assert error.error_code == ValidationErrorCode.DEPENDENCY_MISSING
        assert error.severity == ValidationSeverity.ERROR
        assert error.component == "missing_stage"
        assert "not found in dependency definitions" in error.message
        assert error.context["missing_stage"] == "missing_stage"

    def test_service_unavailable_error(self):
        """Test creating service unavailable error."""
        error = ValidationErrorBuilder.service_unavailable("component", "API Service", "http://api.example.com")

        assert error.error_code == ValidationErrorCode.SERVICE_UNAVAILABLE
        assert error.severity == ValidationSeverity.ERROR
        assert error.component == "component"
        assert "API Service" in error.message
        assert "http://api.example.com" in error.message
        assert error.context["service"] == "API Service"
        assert error.context["url"] == "http://api.example.com"


class TestValidationErrorStructure:
    """Test ValidationError data structure and methods."""

    def test_validation_error_str_representation(self):
        """Test string representation of ValidationError."""
        error = ValidationError(
            error_code=ValidationErrorCode.ENV_VAR_MISSING,
            severity=ValidationSeverity.ERROR,
            component="test_component",
            message="Test error message",
            context={"key": "value"},
            remediation_steps=["Step 1", "Step 2"]
        )

        error_str = str(error)
        assert "❌" in error_str  # Error icon
        assert "ENV_001" in error_str  # Error code
        assert "test_component" in error_str
        assert "Test error message" in error_str

    def test_validation_error_to_dict(self):
        """Test converting ValidationError to dictionary."""
        error = ValidationError(
            error_code=ValidationErrorCode.DATABASE_CONNECTION_FAILED,
            severity=ValidationSeverity.CRITICAL,
            component="database",
            message="Connection failed",
            context={"error": "timeout"},
            remediation_steps=["Check connection"]
        )

        error_dict = error.to_dict()
        assert error_dict["error_code"] == "DB_001"
        assert error_dict["severity"] == "critical"
        assert error_dict["component"] == "database"
        assert error_dict["message"] == "Connection failed"
        assert error_dict["context"]["error"] == "timeout"
        assert "Check connection" in error_dict["remediation_steps"]

    def test_validation_error_severity_icons(self):
        """Test that different severities produce different icons."""
        critical_error = ValidationError(
            error_code=ValidationErrorCode.DATABASE_CONNECTION_FAILED,
            severity=ValidationSeverity.CRITICAL,
            component="test",
            message="Critical error"
        )

        error_error = ValidationError(
            error_code=ValidationErrorCode.ENV_VAR_MISSING,
            severity=ValidationSeverity.ERROR,
            component="test",
            message="Error message"
        )

        warning_error = ValidationError(
            error_code=ValidationErrorCode.ENV_VAR_MISSING,
            severity=ValidationSeverity.WARNING,
            component="test",
            message="Warning message"
        )

        info_error = ValidationError(
            error_code=ValidationErrorCode.ENV_VAR_MISSING,
            severity=ValidationSeverity.INFO,
            component="test",
            message="Info message"
        )

        assert "🔴" in str(critical_error)
        assert "❌" in str(error_error)
        assert "⚠️" in str(warning_error)
        assert "ℹ️" in str(info_error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
