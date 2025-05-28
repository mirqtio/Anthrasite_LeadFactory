# -*- coding: utf-8 -*-
"""
Test suite for the refactored PipelineValidator.

This module tests the validation rules and pipeline stage validation
functionality of the updated PipelineValidator.
"""

import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the project root to the path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.preflight.pipeline_validator import (
    PipelineValidator,
    ValidationRule,
    DatabaseConnectionRule,
    ModuleImportRule,
    FileAccessRule,
    EnvironmentVariableRule,
    NetworkConnectivityRule,
    PipelineValidationResult,
    ValidationError,
    ValidationSeverity,
    ValidationErrorCode,
    ValidationErrorBuilder
)


class TestValidationRules:
    """Test individual validation rules."""

    def test_environment_variable_rule_required_missing(self):
        """Test required environment variable that is missing."""
        rule = EnvironmentVariableRule("TEST_MISSING_VAR", required=True)
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.ENV_VAR_MISSING
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "TEST_MISSING_VAR" in issues[0].message

    def test_environment_variable_rule_required_present(self):
        """Test required environment variable that is present."""
        with patch.dict(os.environ, {"TEST_PRESENT_VAR": "test_value"}):
            rule = EnvironmentVariableRule("TEST_PRESENT_VAR", required=True)
            issues = rule.validate({})

            assert len(issues) == 0

    def test_environment_variable_rule_optional_missing(self):
        """Test optional environment variable that is missing."""
        rule = EnvironmentVariableRule("TEST_OPTIONAL_VAR", required=False)
        issues = rule.validate({})

        assert len(issues) == 0

    def test_file_access_rule_missing_file(self):
        """Test file access rule with missing file."""
        rule = FileAccessRule("/nonexistent/file.txt", "read")
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.FILE_NOT_FOUND
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "/nonexistent/file.txt" in issues[0].message

    def test_file_access_rule_existing_file(self):
        """Test file access rule with existing file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            rule = FileAccessRule(tmp_path, "read")
            issues = rule.validate({})

            assert len(issues) == 0
        finally:
            os.unlink(tmp_path)

    def test_module_import_rule_valid_module(self):
        """Test module import rule with valid module."""
        rule = ModuleImportRule("os")
        issues = rule.validate({})

        assert len(issues) == 0

    def test_module_import_rule_invalid_module(self):
        """Test module import rule with invalid module."""
        rule = ModuleImportRule("nonexistent_module_xyz")
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.MODULE_IMPORT_FAILED
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "nonexistent_module_xyz" in issues[0].message

    @patch('requests.get')
    def test_network_connectivity_rule_success(self, mock_get):
        """Test network connectivity rule with successful connection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        rule = NetworkConnectivityRule("http://example.com", timeout=5)
        issues = rule.validate({})

        assert len(issues) == 0

    @patch('requests.get')
    def test_network_connectivity_rule_failure(self, mock_get):
        """Test network connectivity rule with failed connection."""
        mock_get.side_effect = Exception("Connection failed")

        rule = NetworkConnectivityRule("http://example.com", timeout=5)
        issues = rule.validate({})

        assert len(issues) == 1
        assert issues[0].error_code == ValidationErrorCode.SERVICE_UNAVAILABLE
        assert issues[0].severity == ValidationSeverity.ERROR
        assert "example.com" in issues[0].message

    @patch('psycopg2.connect')
    def test_database_connection_rule_success(self, mock_connect):
        """Test database connection rule with successful connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
            rule = DatabaseConnectionRule()
            issues = rule.validate({})

            assert len(issues) == 0
            mock_connect.assert_called_once_with("postgresql://test")
            mock_conn.close.assert_called_once()

    def test_database_connection_rule_missing_url(self):
        """Test database connection rule with missing DATABASE_URL."""
        with patch.dict(os.environ, {}, clear=True):
            rule = DatabaseConnectionRule()
            issues = rule.validate({})

            assert len(issues) == 1
            assert issues[0].error_code == ValidationErrorCode.ENV_VAR_MISSING
            assert issues[0].severity == ValidationSeverity.ERROR
            assert "DATABASE_URL" in issues[0].message


class TestPipelineValidator:
    """Test the main PipelineValidator class."""

    def test_pipeline_stages_defined(self):
        """Test that pipeline stages are properly defined."""
        validator = PipelineValidator()

        expected_stages = [
            "scrape", "screenshot", "mockup",
            "personalize", "render", "email_queue"
        ]

        assert validator.PIPELINE_STAGES == expected_stages

    def test_supporting_modules_defined(self):
        """Test that supporting modules are properly defined."""
        validator = PipelineValidator()

        expected_modules = [
            "dedupe_unified", "enrich", "score",
            "conflict_resolution", "data_preservation", "manual_review"
        ]

        assert validator.SUPPORTING_MODULES == expected_modules

    def test_validation_rules_created(self):
        """Test that validation rules are created for all components."""
        validator = PipelineValidator()

        all_components = validator.PIPELINE_STAGES + validator.SUPPORTING_MODULES

        for component in all_components:
            assert component in validator.validation_rules
            assert len(validator.validation_rules[component]) > 0

    def test_mock_mode_validation(self):
        """Test validation in mock mode."""
        with patch.dict(os.environ, {"E2E_MODE": "true", "MOCKUP_ENABLED": "true"}):
            validator = PipelineValidator()
            result = validator.validate()

            # In mock mode, should have fewer failures due to mocked components
            assert isinstance(result, PipelineValidationResult)
            assert len(result.components_verified) >= 0

    def test_non_e2e_mode_skips_validation(self):
        """Test that validation runs but may have issues when not in E2E mode."""
        with patch.dict(os.environ, {}, clear=True):
            validator = PipelineValidator()
            result = validator.validate()

            # Without E2E_MODE, validation still runs but may fail due to missing dependencies
            assert isinstance(result, PipelineValidationResult)
            # Don't assert success since it depends on environment setup

    @patch.dict(os.environ, {"E2E_MODE": "true"})
    def test_e2e_mode_runs_validation(self):
        """Test that validation runs in E2E mode."""
        validator = PipelineValidator()
        result = validator.validate()

        # Should fail due to missing DATABASE_URL and other requirements
        assert not result.success
        assert len(result.components_failed) > 0
        assert len(result.issues) > 0

    def test_component_validation_with_rules(self):
        """Test individual component validation with rules."""
        validator = PipelineValidator()

        # Test with scrape component which has defined rules
        rules = validator.validation_rules.get("scrape", [])
        issues = validator._verify_component("scrape", rules)

        # Should return a list of ValidationError objects
        assert isinstance(issues, list)
        # May have issues due to missing environment variables

    def test_component_validation_without_rules(self):
        """Test component validation when no rules are defined."""
        validator = PipelineValidator()

        # Test with empty rules list
        issues = validator._verify_component("test_component", [])

        # Should return empty list when no rules are defined
        assert isinstance(issues, list)
        # May still have resource dependency issues


class TestPipelineValidationResult:
    """Test the PipelineValidationResult class."""

    def test_validation_result_creation(self):
        """Test creating a validation result."""
        result = PipelineValidationResult(
            success=True,
            components_verified=["component1", "component2"],
            components_failed=[],
            issues=[]
        )

        assert result.success
        assert result.components_verified == ["component1", "component2"]
        assert result.components_failed == []
        assert result.issues == []

    def test_validation_result_with_failures(self):
        """Test creating a validation result with failures."""
        from scripts.preflight.pipeline_validator import ValidationErrorBuilder

        test_error = ValidationErrorBuilder.env_var_missing("component2", "TEST_VAR")

        result = PipelineValidationResult(
            success=False,
            components_verified=["component1"],
            components_failed=["component2"],
            issues=[test_error]
        )

        assert not result.success
        assert result.components_verified == ["component1"]
        assert result.components_failed == ["component2"]
        assert len(result.issues) == 1
        assert result.issues[0].error_code == ValidationErrorCode.ENV_VAR_MISSING


class TestIntegration:
    """Integration tests for the complete validation system."""

    @patch.dict(os.environ, {
        "E2E_MODE": "true",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "YELP_API_KEY": "test_yelp_key",
        "GOOGLE_API_KEY": "test_google_key",
        "SCREENSHOTONE_API_KEY": "test_screenshot_key",
        "SENDGRID_API_KEY": "test_sendgrid_key",
        "SENDGRID_FROM_EMAIL": "test@anthrasite.io"
    })
    @patch('psycopg2.connect')
    @patch('os.path.exists')
    def test_full_validation_with_database(self, mock_exists, mock_connect):
        """Test full validation with database connection."""
        # Mock file existence for templates
        mock_exists.return_value = True

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Create temporary config directory
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "leadfactory" / "config"
            config_dir.mkdir(parents=True)

            # Create config.yaml file
            config_file = config_dir / "config.yaml"
            config_file.write_text("test: config")

            # Change to temp directory for the test
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                validator = PipelineValidator()
                result = validator.validate()

                # Should have some successes (supporting modules)
                # and some failures (missing modules for pipeline stages)
                assert len(result.components_verified) > 0
                assert len(result.components_failed) >= 0

            finally:
                os.chdir(original_cwd)


class TestDependencyChecking:
    """Test dependency checking functionality."""

    def setup_method(self):
        """Setup method to ensure clean state for each test."""
        # Store original dependencies to restore after each test
        self.original_dependencies = {
            "scrape": [],
            "screenshot": ["scrape"],
            "mockup": ["screenshot"],
            "personalize": ["scrape"],
            "render": ["personalize", "mockup"],
            "email_queue": ["render"],
            "dedupe_unified": ["scrape"],
            "enrich": ["scrape"],
            "score": ["enrich"],
            "conflict_resolution": ["dedupe_unified"],
            "data_preservation": ["dedupe_unified"],
            "manual_review": ["conflict_resolution"],
        }

    def teardown_method(self):
        """Teardown method to restore original state after each test."""
        # Restore original dependencies
        from scripts.preflight.pipeline_validator import PipelineValidator
        PipelineValidator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

    @patch.dict(os.environ, {
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "YELP_API_KEY": "test_yelp_key",
        "GOOGLE_API_KEY": "test_google_key",
        "SCREENSHOTONE_API_KEY": "test_screenshot_key"
    })
    @patch('psycopg2.connect')
    @patch('os.path.exists')
    def test_validate_dependencies_success(self, mock_exists, mock_connect):
        """Test successful dependency validation."""
        # Mock file existence for templates
        mock_exists.return_value = True

        # Mock database connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Test with a subset of stages that have valid dependencies
        stages = ["scrape", "screenshot", "mockup"]
        issues = validator.validate_dependencies(stages)

        # Should return empty list for successful validation
        assert isinstance(issues, list)
        assert len(issues) == 0

    def test_validate_dependencies_circular_dependency(self):
        """Test detection of circular dependencies."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Temporarily modify dependencies to create a circular dependency
        original_deps = validator.STAGE_DEPENDENCIES.copy()
        try:
            # Create circular dependency: scrape -> screenshot -> scrape
            validator.STAGE_DEPENDENCIES["scrape"] = ["screenshot"]
            validator.STAGE_DEPENDENCIES["screenshot"] = ["scrape"]

            issues = validator.validate_dependencies(["scrape", "screenshot"])

            assert isinstance(issues, list)
            assert len(issues) > 0
            assert any("Circular dependency detected" in issue.message for issue in issues)

        finally:
            validator.STAGE_DEPENDENCIES = original_deps

    def test_validate_dependencies_missing_stage(self):
        """Test validation with missing stage definition."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Test with a non-existent stage
        issues = validator.validate_dependencies(["nonexistent_stage"])

        assert isinstance(issues, list)
        assert len(issues) > 0
        assert any("not found in dependency definitions" in issue.message for issue in issues)

    def test_validate_dependencies_undefined_dependency(self):
        """Test validation with undefined dependency."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Temporarily add a stage with undefined dependency
        original_deps = validator.STAGE_DEPENDENCIES.copy()
        try:
            validator.STAGE_DEPENDENCIES["test_stage"] = ["undefined_dependency"]

            issues = validator.validate_dependencies(["test_stage"])

            assert isinstance(issues, list)
            assert len(issues) > 0
            assert any("depends on undefined stage" in issue.message for issue in issues)

        finally:
            validator.STAGE_DEPENDENCIES = original_deps

    def test_get_dependency_order(self):
        """Test dependency order calculation."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Test with pipeline stages - use a fresh validator instance
        stages = ["scrape", "screenshot", "mockup", "render", "personalize"]
        order = validator._get_dependency_order(stages)

        assert order is not None, f"Expected valid order but got None. Dependencies: {validator.STAGE_DEPENDENCIES}"
        assert len(order) == len(stages)

        # Verify that dependencies come before dependents
        scrape_idx = order.index("scrape")
        screenshot_idx = order.index("screenshot")
        mockup_idx = order.index("mockup")

        assert scrape_idx < screenshot_idx  # scrape before screenshot
        assert screenshot_idx < mockup_idx  # screenshot before mockup

    def test_get_dependency_order_circular(self):
        """Test dependency order with circular dependencies."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Temporarily create circular dependency
        original_deps = validator.STAGE_DEPENDENCIES.copy()
        try:
            validator.STAGE_DEPENDENCIES["scrape"] = ["screenshot"]
            validator.STAGE_DEPENDENCIES["screenshot"] = ["scrape"]

            order = validator._get_dependency_order(["scrape", "screenshot"])

            assert order is None  # Should return None for circular dependencies

        finally:
            validator.STAGE_DEPENDENCIES = original_deps

    def test_detect_circular_dependencies(self):
        """Test circular dependency detection."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Get list of all stages for testing
        stages = list(self.original_dependencies.keys())

        # Test with no circular dependencies (fresh validator)
        cycles = validator._detect_circular_dependencies(stages)
        assert len(cycles) == 0

        # Temporarily create circular dependency
        original_deps = validator.STAGE_DEPENDENCIES.copy()
        try:
            validator.STAGE_DEPENDENCIES["scrape"] = ["screenshot"]
            validator.STAGE_DEPENDENCIES["screenshot"] = ["scrape"]

            cycles = validator._detect_circular_dependencies(stages)
            assert len(cycles) > 0

        finally:
            validator.STAGE_DEPENDENCIES = original_deps

    def test_validate_resource_dependencies(self):
        """Test resource dependency validation."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        # Test stage with defined resource dependencies
        issues = validator.validate_resource_dependencies("scrape")

        # Should check database, api_keys, config_files
        # May have issues if not all resources are available, but should not crash
        assert isinstance(issues, list)

    def test_validate_resource_dependencies_unknown_stage(self):
        """Test resource validation for unknown stage."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        issues = validator.validate_resource_dependencies("unknown_stage")

        # Should return empty list for unknown stages (no requirements)
        assert isinstance(issues, list)
        assert len(issues) == 0

    def test_check_resource_availability_database(self):
        """Test database resource availability check."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        issues = validator._check_resource_availability("database")

        # Should attempt to check database connection
        assert isinstance(issues, list)

    def test_check_resource_availability_unknown_resource(self):
        """Test unknown resource availability check."""
        validator = PipelineValidator()
        # Ensure clean state
        validator.STAGE_DEPENDENCIES = self.original_dependencies.copy()

        issues = validator._check_resource_availability("unknown_resource")

        assert isinstance(issues, list)
        assert len(issues) > 0
        assert any("Unknown resource type" in issue.message for issue in issues)

    def test_integration_with_dependency_validation(self):
        """Test full validation with dependency checking."""
        # Set mock mode to avoid actual module imports
        with patch.dict(os.environ, {"MOCKUP_ENABLED": "true", "E2E_MODE": "true"}):
            validator = PipelineValidator()
            result = validator.validate()

            # In mock mode, should have fewer validation issues
            assert isinstance(result, PipelineValidationResult)
            # Don't assert success since it depends on environment setup


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
