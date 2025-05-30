"""
Pipeline Component Validator

This module verifies that all pipeline services and components are properly
configured and operational before running E2E tests.
"""

import importlib.util
import json
import logging
import os
import re
import subprocess
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation errors."""

    CRITICAL = "critical"  # Blocks pipeline execution
    ERROR = "error"  # Causes component failure
    WARNING = "warning"  # May cause issues but not blocking
    INFO = "info"  # Informational only


class ValidationErrorCode(Enum):
    """Standardized error codes for validation failures."""

    # Environment and Configuration
    ENV_VAR_MISSING = "ENV_001"
    ENV_VAR_INVALID = "ENV_002"
    CONFIG_FILE_MISSING = "CFG_001"
    CONFIG_FILE_INVALID = "CFG_002"

    # Database
    DATABASE_CONNECTION_FAILED = "DB_001"
    DATABASE_URL_MISSING = "DB_002"
    DATABASE_QUERY_FAILED = "DB_003"

    # API and Network
    API_KEY_MISSING = "API_001"  # pragma: allowlist secret
    API_KEY_INVALID = "API_002"  # pragma: allowlist secret
    NETWORK_UNREACHABLE = "NET_001"
    SERVICE_UNAVAILABLE = "NET_002"

    # File System
    FILE_NOT_FOUND = "FS_001"
    FILE_PERMISSION_DENIED = "FS_002"
    DIRECTORY_NOT_FOUND = "FS_003"

    # Module and Import
    MODULE_IMPORT_FAILED = "MOD_001"
    MODULE_NOT_FOUND = "MOD_002"

    # Dependencies
    DEPENDENCY_CIRCULAR = "DEP_001"
    DEPENDENCY_MISSING = "DEP_002"
    DEPENDENCY_UNRESOLVED = "DEP_003"

    # Resource Availability
    RESOURCE_UNAVAILABLE = "RES_001"
    RESOURCE_INSUFFICIENT = "RES_002"


@dataclass
class ValidationError:
    """Structured validation error with context and remediation."""

    error_code: ValidationErrorCode
    severity: ValidationSeverity
    component: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    remediation_steps: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Human-readable error message."""
        severity_icon = {
            ValidationSeverity.CRITICAL: "🔴",
            ValidationSeverity.ERROR: "❌",
            ValidationSeverity.WARNING: "⚠️",
            ValidationSeverity.INFO: "ℹ️",
        }

        icon = severity_icon.get(self.severity, "•")
        return f"{icon} [{self.error_code.value}] {self.component}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for JSON serialization."""
        return {
            "error_code": self.error_code.value,
            "severity": self.severity.value,
            "component": self.component,
            "message": self.message,
            "context": self.context,
            "remediation_steps": self.remediation_steps,
        }


class ValidationErrorBuilder:
    """Builder class for creating structured validation errors."""

    @staticmethod
    def env_var_missing(component: str, var_name: str) -> ValidationError:
        """Create error for missing environment variable."""
        return ValidationError(
            error_code=ValidationErrorCode.ENV_VAR_MISSING,
            severity=ValidationSeverity.ERROR,
            component=component,
            message=f"Required environment variable '{var_name}' is not set",
            context={"variable": var_name},
            remediation_steps=[
                f"Set the {var_name} environment variable",
                f"Add {var_name}=<value> to your .env file",
                "Ensure the .env file is loaded before running the pipeline",
            ],
        )

    @staticmethod
    def api_key_missing(component: str, api_keys: list[str]) -> ValidationError:
        """Create error for missing API keys with enhanced context."""
        keys_str = ", ".join(api_keys)
        return ValidationError(
            error_code=ValidationErrorCode.API_KEY_MISSING,
            severity=ValidationSeverity.ERROR,
            component=component,
            message=f"Component '{component}' requires missing API keys: {keys_str}",
            context={
                "missing_keys": api_keys,
                "component": component,
                "key_count": len(api_keys),
            },
            remediation_steps=[
                f"Obtain valid API keys for: {keys_str}",
                "Add the API keys to your .env file with correct variable names",
                "Verify the API keys are valid and have not expired",
                "Check API key permissions and rate limits",
                "Ensure API keys have access to required services/endpoints",
                f"Test API connectivity for {component} before running pipeline",
            ],
        )

    @staticmethod
    def database_connection_failed(component: str, error: str) -> ValidationError:
        """Create error for database connection failure."""
        return ValidationError(
            error_code=ValidationErrorCode.DATABASE_CONNECTION_FAILED,
            severity=ValidationSeverity.CRITICAL,
            component=component,
            message=f"Database connection failed: {error}",
            context={"error": error},
            remediation_steps=[
                "Verify DATABASE_URL is correctly set",
                "Check database server is running and accessible",
                "Verify database credentials are correct",
                "Check network connectivity to database server",
                "Ensure database exists and user has proper permissions",
            ],
        )

    @staticmethod
    def file_not_found(component: str, file_path: str) -> ValidationError:
        """Create error for missing file."""
        return ValidationError(
            error_code=ValidationErrorCode.FILE_NOT_FOUND,
            severity=ValidationSeverity.ERROR,
            component=component,
            message=f"Required file not found: {file_path}",
            context={"file_path": file_path},
            remediation_steps=[
                f"Create the missing file: {file_path}",
                "Verify the file path is correct",
                "Check file permissions and accessibility",
                "Ensure the file is in the expected location",
            ],
        )

    @staticmethod
    def module_import_failed(
        component: str, module_path: str, error: str
    ) -> ValidationError:
        """Create error for module import failure."""
        return ValidationError(
            error_code=ValidationErrorCode.MODULE_IMPORT_FAILED,
            severity=ValidationSeverity.ERROR,
            component=component,
            message=f"Failed to import {module_path}: {error}",
            context={"module_path": module_path, "error": error},
            remediation_steps=[
                f"Ensure the module {module_path} exists",
                "Check for syntax errors in the module",
                "Verify all module dependencies are installed",
                "Check Python path and module visibility",
                "Install missing dependencies with pip",
            ],
        )

    @staticmethod
    def dependency_circular(component: str, cycle: list[str]) -> ValidationError:
        """Create error for circular dependency detection."""
        cycle_str = " -> ".join(cycle + [cycle[0]])  # Show complete cycle
        return ValidationError(
            error_code=ValidationErrorCode.DEPENDENCY_CIRCULAR,
            severity=ValidationSeverity.CRITICAL,
            component=component,
            message=f"Circular dependency detected in pipeline stages: {cycle_str}",
            context={
                "cycle": cycle,
                "cycle_length": len(cycle),
                "affected_stages": cycle,
            },
            remediation_steps=[
                "Review pipeline stage dependencies to identify the circular reference",
                f"Examine dependencies for stages: {', '.join(cycle)}",
                "Remove or restructure dependencies to break the cycle",
                "Consider using conditional dependencies or stage ordering",
                "Verify that stage execution order is logically correct",
                "Update STAGE_DEPENDENCIES configuration to resolve conflicts",
            ],
        )

    @staticmethod
    def circular_dependency(component: str, cycle: list[str]) -> ValidationError:
        """Create error for circular dependency (legacy method)."""
        return ValidationErrorBuilder.dependency_circular(component, cycle)

    @staticmethod
    def dependency_missing(component: str, missing_deps: list[str]) -> ValidationError:
        """Create error for missing dependencies with enhanced context."""
        if not missing_deps:
            # Handle case where the stage itself doesn't exist
            return ValidationError(
                error_code=ValidationErrorCode.DEPENDENCY_MISSING,
                severity=ValidationSeverity.ERROR,
                component=component,
                message=f"Pipeline stage '{component}' not found in dependency definitions",
                context={
                    "missing_stage": component,
                    "available_stages": [],  # Will be populated by caller if needed
                },
                remediation_steps=[
                    f"Add '{component}' to the STAGE_DEPENDENCIES configuration",
                    "Verify that the stage name is spelled correctly",
                    "Check if the stage should be part of the pipeline execution",
                    "Review pipeline configuration for missing stage definitions",
                    "Ensure all required stages are properly configured",
                ],
            )

        deps_str = ", ".join(missing_deps)
        return ValidationError(
            error_code=ValidationErrorCode.DEPENDENCY_MISSING,
            severity=ValidationSeverity.ERROR,
            component=component,
            message=f"Pipeline stage '{component}' depends on undefined stage(s): {deps_str}",
            context={
                "missing_dependencies": missing_deps,
                "component": component,
                "dependency_count": len(missing_deps),
            },
            remediation_steps=[
                f"Implement or configure the missing dependencies: {deps_str}",
                f"Verify that dependencies for '{component}' are properly defined",
                "Check STAGE_DEPENDENCIES configuration for correct mappings",
                "Ensure all required pipeline stages are included in the execution plan",
                "Review pipeline execution order to include missing stages",
                "Update pipeline configuration to resolve dependency requirements",
            ],
        )

    @staticmethod
    def service_unavailable(component: str, service: str, url: str) -> ValidationError:
        """Create error for unavailable service."""
        return ValidationError(
            error_code=ValidationErrorCode.SERVICE_UNAVAILABLE,
            severity=ValidationSeverity.ERROR,
            component=component,
            message=f"Service {service} is unavailable at {url}",
            context={"service": service, "url": url},
            remediation_steps=[
                f"Verify {service} service is running",
                "Check network connectivity to the service",
                "Verify service URL and configuration",
                "Check service health and status",
                "Review firewall and security settings",
            ],
        )


class ValidationLogger:
    """Logger for validation errors to facilitate debugging."""

    def __init__(self, logger_name: str = "pipeline_validator"):
        self.logger = logging.getLogger(logger_name)
        self.validation_session_id = str(uuid.uuid4())[:8]
        self.error_count = 0
        self.warning_count = 0

    def log_validation_start(self, component: str):
        """Log the start of validation for a component."""
        self.logger.info(
            f"🔍 Starting validation for component: {component} [Session: {self.validation_session_id}]"
        )

    def log_validation_error(self, error: ValidationError):
        """Log a validation error with structured information."""
        self.error_count += 1
        severity_icon = {
            ValidationSeverity.CRITICAL: "🔴",
            ValidationSeverity.ERROR: "❌",
            ValidationSeverity.WARNING: "⚠️",
            ValidationSeverity.INFO: "ℹ️",
        }.get(error.severity, "❓")

        self.logger.error(
            f"{severity_icon} [{error.error_code.value}] {error.component}: {error.message}"
        )

        if error.context:
            self.logger.error(f"   Context: {error.context}")

        if error.remediation_steps:
            self.logger.error("   Remediation steps:")
            for i, step in enumerate(error.remediation_steps, 1):
                self.logger.error(f"   {i}. {step}")

    def log_validation_success(self, component: str):
        """Log successful validation for a component."""
        self.logger.info(f"✅ Validation successful for component: {component}")

    def log_validation_summary(
        self, total_components: int, failed_components: int, total_errors: int
    ):
        """Log a summary of the validation session."""
        success_rate = (
            ((total_components - failed_components) / total_components * 100)
            if total_components > 0
            else 0
        )

        self.logger.info(
            f"📊 Validation Summary [Session: {self.validation_session_id}]:"
        )
        self.logger.info(f"   Total components: {total_components}")
        self.logger.info(f"   Successful: {total_components - failed_components}")
        self.logger.info(f"   Failed: {failed_components}")
        self.logger.info(f"   Success rate: {success_rate:.1f}%")
        self.logger.info(f"   Total errors: {total_errors}")

        if failed_components == 0:
            self.logger.info("🎉 All validations passed successfully!")
        else:
            self.logger.error(f"💥 {failed_components} component(s) failed validation")


class ValidationRule:
    """Base class for validation rules."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def validate(self, context: dict[str, Any]) -> list[ValidationError]:
        """Validate the rule and return list of validation errors."""
        raise NotImplementedError("Subclasses must implement validate method")


class DatabaseConnectionRule(ValidationRule):
    """Validates database connectivity."""

    def __init__(self):
        super().__init__("database_connection", "Database connectivity check")

    def validate(self, context: dict[str, Any]) -> list[ValidationError]:
        """Validate database connection."""
        issues = []

        # Check for required environment variables
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            issues.append(
                ValidationErrorBuilder.env_var_missing("database", "DATABASE_URL")
            )
            return issues

        try:
            # Try to import and test database connection
            import psycopg2

            conn = psycopg2.connect(db_url)
            conn.close()
            logger.info("✅ Database connection successful")
            return []
        except ImportError:
            issues.append(
                ValidationErrorBuilder.module_import_failed(
                    "database", "psycopg2", "psycopg2 not installed"
                )
            )
            return issues
        except Exception as e:
            issues.append(
                ValidationErrorBuilder.database_connection_failed("database", str(e))
            )
            return issues


class ModuleImportRule(ValidationRule):
    """Validates that required modules can be imported."""

    def __init__(self, module_path: str):
        self.module_path = module_path
        super().__init__(
            f"module_import_{module_path}", f"Import check for {module_path}"
        )

    def validate(self, context: dict[str, Any]) -> list[ValidationError]:
        """Validate module import."""
        issues = []

        try:
            # Try to import the module
            spec = importlib.util.find_spec(self.module_path)
            if spec is None:
                issues.append(
                    ValidationErrorBuilder.module_import_failed(
                        self.module_path, self.module_path, "Module not found"
                    )
                )
                return issues

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            logger.info(f"✅ Module {self.module_path} imported successfully")
            return []
        except Exception as e:
            issues.append(
                ValidationErrorBuilder.module_import_failed(
                    self.module_path, self.module_path, str(e)
                )
            )
            return issues


class FileAccessRule(ValidationRule):
    """Validates file system access."""

    def __init__(self, path: str, access_type: str = "read"):
        self.path = path
        self.access_type = access_type
        super().__init__(f"file_access_{path}", f"File access check for {path}")

    def validate(self, context: dict[str, Any]) -> list[ValidationError]:
        """Validate file access."""
        issues = []

        path_obj = Path(self.path)

        if not path_obj.exists():
            issues.append(ValidationErrorBuilder.file_not_found(self.path, self.path))
            return issues

        if self.access_type == "read" and not os.access(self.path, os.R_OK):
            issues.append(ValidationErrorBuilder.file_not_found(self.path, self.path))
            return issues

        if self.access_type == "write" and not os.access(self.path, os.W_OK):
            issues.append(ValidationErrorBuilder.file_not_found(self.path, self.path))
            return issues

        logger.info(f"✅ {self.access_type.title()} access to {self.path} confirmed")
        return []


class EnvironmentVariableRule(ValidationRule):
    """Validates required environment variables."""

    def __init__(self, var_name: str, required: bool = True):
        self.var_name = var_name
        self.required = required
        super().__init__(
            f"env_var_{var_name}", f"Environment variable check for {var_name}"
        )

    def validate(self, context: dict[str, Any]) -> list[ValidationError]:
        """Validate environment variable."""
        issues = []

        value = os.getenv(self.var_name)

        if self.required and not value:
            issues.append(
                ValidationErrorBuilder.env_var_missing(self.var_name, self.var_name)
            )
            return issues

        if value:
            logger.info(f"✅ Environment variable {self.var_name} is set")

        return []


class NetworkConnectivityRule(ValidationRule):
    """Validates network connectivity to external services."""

    def __init__(self, url: str, timeout: int = 5):
        self.url = url
        self.timeout = timeout
        super().__init__(f"network_{url}", f"Network connectivity check for {url}")

    def validate(self, context: dict[str, Any]) -> list[ValidationError]:
        """Validate network connectivity."""
        issues = []

        try:
            response = requests.get(self.url, timeout=self.timeout)
            if response.status_code == 200:
                logger.info(f"✅ Network connectivity to {self.url} successful")
                return []
            else:
                issues.append(
                    ValidationErrorBuilder.service_unavailable(
                        self.url, "service", self.url
                    )
                )
                return issues
        except Exception:
            issues.append(
                ValidationErrorBuilder.service_unavailable(
                    self.url, "service", self.url
                )
            )
            return issues


class PipelineValidationResult:
    """Result of pipeline component validation."""

    def __init__(
        self,
        success: bool,
        components_verified: list[str],
        components_failed: list[str],
        issues: list[ValidationError],
    ):
        self.success = success
        self.components_verified = components_verified
        self.components_failed = components_failed
        self.issues = issues

    def __str__(self) -> str:
        """String representation of the validation result."""
        if self.success:
            return "✅ Pipeline component validation successful"

        result = "❌ Pipeline component validation failed\n"

        # Group errors by severity
        critical_errors = [
            e for e in self.issues if e.severity == ValidationSeverity.CRITICAL
        ]
        errors = [e for e in self.issues if e.severity == ValidationSeverity.ERROR]
        warnings = [e for e in self.issues if e.severity == ValidationSeverity.WARNING]

        if critical_errors:
            result += "\n🔴 CRITICAL ERRORS:\n"
            for error in critical_errors:
                result += f"  {error}\n"
                if error.remediation_steps:
                    result += "    Remediation:\n"
                    for step in error.remediation_steps:
                        result += f"      • {step}\n"

        if errors:
            result += "\n❌ ERRORS:\n"
            for error in errors:
                result += f"  {error}\n"
                if error.remediation_steps:
                    result += "    Remediation:\n"
                    for step in error.remediation_steps:
                        result += f"      • {step}\n"

        if warnings:
            result += "\n⚠️ WARNINGS:\n"
            for warning in warnings:
                result += f"  {warning}\n"
                if warning.remediation_steps:
                    result += "    Remediation:\n"
                    for step in warning.remediation_steps:
                        result += f"      • {step}\n"

        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "components_verified": self.components_verified,
            "components_failed": self.components_failed,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": {
                "total_issues": len(self.issues),
                "critical_count": len(
                    [
                        e
                        for e in self.issues
                        if e.severity == ValidationSeverity.CRITICAL
                    ]
                ),
                "error_count": len(
                    [e for e in self.issues if e.severity == ValidationSeverity.ERROR]
                ),
                "warning_count": len(
                    [e for e in self.issues if e.severity == ValidationSeverity.WARNING]
                ),
                "info_count": len(
                    [e for e in self.issues if e.severity == ValidationSeverity.INFO]
                ),
            },
        }

    def get_errors_by_component(self) -> dict[str, list[ValidationError]]:
        """Group errors by component for easier analysis."""
        errors_by_component = {}
        for error in self.issues:
            if error.component not in errors_by_component:
                errors_by_component[error.component] = []
            errors_by_component[error.component].append(error)
        return errors_by_component

    def get_errors_by_severity(self) -> dict[ValidationSeverity, list[ValidationError]]:
        """Group errors by severity level."""
        errors_by_severity = {severity: [] for severity in ValidationSeverity}
        for error in self.issues:
            errors_by_severity[error.severity].append(error)
        return errors_by_severity

    def has_blocking_errors(self) -> bool:
        """Check if there are any critical or error-level issues that would block execution."""
        return any(
            issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]
            for issue in self.issues
        )


class PipelineValidator:
    """Validates pipeline components for E2E testing."""

    # Define actual pipeline stages with their dependencies
    PIPELINE_STAGES = [
        "scrape",
        "screenshot",
        "mockup",
        "personalize",
        "render",
        "email_queue",
    ]

    # Define supporting modules
    SUPPORTING_MODULES = [
        "dedupe_unified",
        "enrich",
        "score",
        "conflict_resolution",
        "data_preservation",
        "manual_review",
    ]

    # Define stage dependencies (stage -> list of prerequisite stages)
    STAGE_DEPENDENCIES = {
        "scrape": [],  # No dependencies, this is the first stage
        "screenshot": ["scrape"],  # Needs business data from scrape
        "mockup": ["screenshot"],  # Needs screenshot data
        "personalize": ["scrape"],  # Needs business data for personalization
        "render": ["personalize", "mockup"],  # Needs personalized content and mockup
        "email_queue": ["render"],  # Needs rendered email content
        # Supporting modules dependencies
        "dedupe_unified": ["scrape"],  # Needs scraped data to deduplicate
        "enrich": ["scrape"],  # Needs basic business data to enrich
        "score": ["enrich"],  # Needs enriched data for scoring
        "conflict_resolution": ["dedupe_unified"],  # Needs deduplication conflicts
        "data_preservation": ["dedupe_unified"],  # Needs deduplication results
        "manual_review": ["conflict_resolution"],  # Needs unresolved conflicts
    }

    # Define resource dependencies (what resources each stage needs)
    RESOURCE_DEPENDENCIES = {
        "scrape": ["database", "api_keys", "config_files"],
        "screenshot": ["database", "screenshot_api"],
        "mockup": ["database", "mockup_generation"],
        "personalize": ["database", "templates"],
        "render": ["database", "email_templates"],
        "email_queue": ["database", "email_service", "smtp_config"],
        # Supporting modules
        "dedupe_unified": ["database", "dedupe_config"],
        "enrich": ["database", "enrichment_apis"],
        "score": ["database", "scoring_config"],
        "conflict_resolution": ["database"],
        "data_preservation": ["database"],
        "manual_review": ["database"],
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the PipelineValidator.

        Args:
            config_path: Optional path to validation configuration file
        """
        self.config_path = config_path
        self.validation_logger = ValidationLogger()

        # Define stage dependencies
        self.STAGE_DEPENDENCIES = {
            "scrape": [],
            "screenshot": ["scrape"],
            "mockup": ["screenshot"],
            "personalize": ["scrape"],
            "render": ["personalize", "mockup"],
            "email_queue": ["render"],
            "dedupe_unified": ["scrape"],
            "enrich": ["dedupe_unified"],
            "score": ["enrich"],
            "conflict_resolution": ["dedupe_unified"],
            "data_preservation": ["dedupe_unified"],
            "manual_review": ["conflict_resolution"],
        }

        # Define resource dependencies for each stage
        self.RESOURCE_DEPENDENCIES = {
            "scrape": ["database", "api_keys"],
            "screenshot": ["screenshot_api", "database"],
            "mockup": ["mockup_generation", "database"],
            "personalize": ["api_keys", "templates"],
            "render": ["email_templates", "database"],
            "email_queue": ["email_service", "smtp_config", "database"],
            "dedupe_unified": ["database", "dedupe_config"],
            "enrich": ["enrichment_apis", "database"],
            "score": ["scoring_config", "database"],
            "conflict_resolution": ["database"],
            "data_preservation": ["database"],
            "manual_review": ["database"],
        }

        # Load validation rules after dependencies are defined
        self.validation_rules = self._load_validation_rules()

    def _load_validation_rules(self) -> dict[str, list[ValidationRule]]:
        """Load validation rules from configuration."""
        rules = {}

        # Create validation rules for all pipeline stages
        for stage in PipelineValidator.PIPELINE_STAGES:
            rules[stage] = []

            # Add resource dependency rules for each stage
            if stage in self.RESOURCE_DEPENDENCIES:
                for resource in self.RESOURCE_DEPENDENCIES[stage]:
                    if resource == "database":
                        rules[stage].append(DatabaseConnectionRule())
                    elif resource == "api_keys":
                        rules[stage].append(
                            EnvironmentVariableRule("YELP_API_KEY", required=True)
                        )
                        rules[stage].append(
                            EnvironmentVariableRule("GOOGLE_API_KEY", required=True)
                        )
                    elif resource == "screenshot_api":
                        rules[stage].append(
                            EnvironmentVariableRule(
                                "SCREENSHOTONE_API_KEY", required=True
                            )
                        )
                    elif resource == "email_service":
                        rules[stage].append(
                            EnvironmentVariableRule("SENDGRID_API_KEY", required=True)
                        )
                    elif resource == "smtp_config":
                        rules[stage].append(
                            EnvironmentVariableRule(
                                "SENDGRID_FROM_EMAIL", required=True
                            )
                        )
                    elif resource == "email_templates" or resource == "templates":
                        rules[stage].append(FileAccessRule("etc/email_template.html"))
                    # Add more resource-specific rules as needed

        # Create validation rules for supporting modules
        for module in PipelineValidator.SUPPORTING_MODULES:
            rules[module] = []

            # Add resource dependency rules for each supporting module
            if module in self.RESOURCE_DEPENDENCIES:
                for resource in self.RESOURCE_DEPENDENCIES[module]:
                    if resource == "database":
                        rules[module].append(DatabaseConnectionRule())
                    elif resource == "api_keys" or resource == "enrichment_apis":
                        rules[module].append(
                            EnvironmentVariableRule("YELP_API_KEY", required=True)
                        )
                        rules[module].append(
                            EnvironmentVariableRule("GOOGLE_API_KEY", required=True)
                        )
                    elif resource == "scoring_config":
                        rules[module].append(FileAccessRule("etc/scoring_config.yml"))
                    elif resource == "dedupe_config":
                        rules[module].append(FileAccessRule("etc/dedupe_config.yml"))
                    # Add more resource-specific rules as needed

            # Add default rules for modules without specific resource dependencies
            if not rules[module]:  # If no rules were added from resource dependencies
                if module == "network":
                    rules[module].append(NetworkConnectivityRule("google.com", 80))
                else:
                    # Default to database connection for most supporting modules
                    rules[module].append(DatabaseConnectionRule())

        return rules

    def validate_dependencies(
        self, stages: Optional[list[str]] = None
    ) -> list[ValidationError]:
        """Validate all pipeline dependencies including stage dependencies and circular dependency detection.

        Args:
            stages: Optional list of specific stages to validate. If None, validates all stages.

        Returns:
            List of validation errors
        """
        logger.info("Validating pipeline dependencies...")
        issues = []

        # Get components to validate
        if stages is None:
            all_components = list(self.STAGE_DEPENDENCIES.keys())
        else:
            all_components = stages

        # Check for circular dependencies
        try:
            circular_deps = self._detect_circular_dependencies(all_components)
            if circular_deps:
                for cycle in circular_deps.values():
                    issues.append(
                        ValidationErrorBuilder.dependency_circular("pipeline", cycle)
                    )
        except Exception as e:
            issues.append(
                ValidationErrorBuilder.module_import_failed(
                    "pipeline", "dependency_validation", str(e)
                )
            )

        # Check for missing dependencies and undefined stages
        for stage in all_components:
            # Check if stage exists in STAGE_DEPENDENCIES
            if stage not in self.STAGE_DEPENDENCIES:
                # For non-existent stages, create a missing dependency error
                issues.append(ValidationErrorBuilder.dependency_missing(stage, []))
                continue

            dependencies = self.STAGE_DEPENDENCIES.get(stage, [])
            missing_deps = []

            for dep in dependencies:
                if dep not in self.STAGE_DEPENDENCIES:
                    missing_deps.append(dep)

            if missing_deps:
                issues.append(
                    ValidationErrorBuilder.dependency_missing(stage, missing_deps)
                )

        # Validate resource dependencies for each stage that exists
        existing_stages = [
            stage for stage in all_components if stage in self.STAGE_DEPENDENCIES
        ]
        if existing_stages:
            resource_issues = self.validate_resource_dependencies(existing_stages)
            issues.extend(resource_issues)

        if not issues:
            logger.info("✅ All dependencies validated successfully")
        else:
            logger.error(f"❌ Found {len(issues)} dependency issues")

        return issues

    def _detect_circular_dependencies(
        self, components: list[str]
    ) -> dict[str, list[str]]:
        """Detect circular dependencies in the stage dependency graph.

        Returns:
            Dictionary of circular dependency cycles found
        """

        def dfs(node, visited, rec_stack, path, cycles):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.STAGE_DEPENDENCIES.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, visited, rec_stack, path, cycles)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles[node] = cycle

            rec_stack.remove(node)
            path.pop()

        visited = set()
        cycles = {}

        for stage in components:
            if stage not in visited:
                dfs(stage, visited, set(), [], cycles)

        return cycles

    def _get_dependency_order(self, stages: list[str]) -> Optional[list[str]]:
        """Get the correct order to execute stages based on dependencies.

        Args:
            stages: List of stages to order

        Returns:
            Ordered list of stages, or None if circular dependencies exist
        """
        # Topological sort using Kahn's algorithm
        in_degree = dict.fromkeys(stages, 0)
        graph = {stage: [] for stage in stages}

        # Build the graph and calculate in-degrees
        for stage in stages:
            dependencies = self.STAGE_DEPENDENCIES.get(stage, [])
            for dep in dependencies:
                if (
                    dep in stages
                ):  # Only consider dependencies that are in our stage list
                    graph[dep].append(stage)
                    in_degree[stage] += 1

        # Find stages with no dependencies
        queue = [stage for stage in stages if in_degree[stage] == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            # Remove current stage and update in-degrees
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If we processed all stages, no circular dependencies
        if len(result) == len(stages):
            return result
        else:
            return None  # Circular dependencies exist

    def validate_resource_dependencies(
        self, stages: list[str]
    ) -> list[ValidationError]:
        """Validate that all required resources are available for a stage.

        Args:
            stages: List of stages to validate resources for

        Returns:
            List of validation errors
        """
        issues = []

        for stage in stages:
            required_resources = self.RESOURCE_DEPENDENCIES.get(stage, [])
            for resource in required_resources:
                resource_issues = self._check_resource_availability(resource)
                issues.extend(resource_issues)

        return issues

    def _check_resource_availability(self, resource: str) -> list[ValidationError]:
        """
        Check if a specific resource is available.

        Args:
            resource: Resource type to check

        Returns:
            List of validation errors (empty if resource is available)
        """
        issues = []

        if resource == "database":
            # Check database connection using the same approach as DatabaseConnectionRule
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                issues.append(
                    ValidationErrorBuilder.env_var_missing("database", "DATABASE_URL")
                )
            else:
                try:
                    # Try to import and test database connection
                    import psycopg2

                    conn = psycopg2.connect(db_url)
                    conn.close()
                except ImportError:
                    issues.append(
                        ValidationErrorBuilder.module_import_failed(
                            "database", "psycopg2", "psycopg2 not installed"
                        )
                    )
                except Exception as e:
                    issues.append(
                        ValidationErrorBuilder.database_connection_failed(
                            "database", str(e)
                        )
                    )

        elif resource == "api_keys":
            # Check for common API keys
            api_keys = ["YELP_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"]
            missing_keys = [key for key in api_keys if not os.getenv(key)]
            if missing_keys:
                issues.append(
                    ValidationErrorBuilder.api_key_missing("api_keys", missing_keys)
                )

        elif resource == "config_files":
            # Check for configuration files
            config_files = ["leadfactory/config/config.yaml", "leadfactory/config"]
            for config_file in config_files:
                try:
                    rule = FileAccessRule(config_file, "read")
                    rule_issues = rule.validate({})
                    if rule_issues:
                        issues.extend(rule_issues)
                except Exception:
                    issues.append(
                        ValidationErrorBuilder.file_not_found(config_file, config_file)
                    )

        elif resource == "screenshot_api":
            # Check screenshot API configuration
            screenshot_key = os.getenv("SCREENSHOTONE_API_KEY")
            if not screenshot_key:
                issues.append(
                    ValidationErrorBuilder.api_key_missing(
                        "screenshot_api", ["SCREENSHOTONE_API_KEY"]
                    )
                )

        elif resource == "email_service":
            # Check email service configuration
            email_keys = ["SENDGRID_API_KEY", "SMTP_HOST"]
            if not any(os.getenv(key) for key in email_keys):
                issues.append(
                    ValidationErrorBuilder.service_unavailable(
                        "email_service", "email_service", "unknown"
                    )
                )

        elif resource == "templates":
            # Check for email templates
            template_files = ["etc/email_template.html"]
            for template_file in template_files:
                try:
                    rule = FileAccessRule(template_file, "read")
                    rule_issues = rule.validate({})
                    if rule_issues:
                        issues.extend(rule_issues)
                except Exception:
                    issues.append(
                        ValidationErrorBuilder.file_not_found(
                            template_file, template_file
                        )
                    )

        # For other resources, assume they're available (can be extended)
        elif resource in [
            "mockup_generation",
            "email_templates",
            "smtp_config",
            "dedupe_config",
            "enrichment_apis",
            "scoring_config",
        ]:
            # These are internal resources that are typically available
            pass

        else:
            issues.append(
                ValidationError(
                    error_code=ValidationErrorCode.DEPENDENCY_MISSING,
                    severity=ValidationSeverity.WARNING,
                    component=resource,
                    message=f"Unknown resource type: {resource}",
                    context={
                        "resource_type": resource,
                        "known_resources": [
                            "database",
                            "api_keys",
                            "config_files",
                            "screenshot_api",
                            "email_service",
                            "templates",
                            "mockup_generation",
                            "email_templates",
                            "smtp_config",
                            "dedupe_config",
                            "enrichment_apis",
                            "scoring_config",
                        ],
                    },
                    remediation_steps=[
                        f"Verify that '{resource}' is a valid resource type",
                        "Check the resource name for typos",
                        "Add resource validation logic if this is a new resource type",
                        "Review pipeline configuration for correct resource references",
                    ],
                )
            )

        return issues

    def validate(self) -> PipelineValidationResult:
        """
        Validate all pipeline components and their dependencies.

        Returns:
            PipelineValidationResult: Validation results with structured errors
        """
        logger.info("Starting pipeline validation...")

        issues: list[ValidationError] = []
        components_verified = []
        components_failed = []

        # Validate dependencies first
        dependency_issues = self.validate_dependencies()
        issues.extend(dependency_issues)

        # If there are critical dependency issues, stop validation
        critical_dependency_issues = [
            issue
            for issue in dependency_issues
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        if critical_dependency_issues:
            logger.error(
                f"Critical dependency issues found: {len(critical_dependency_issues)}"
            )
            return PipelineValidationResult(
                success=False,
                components_verified=components_verified,
                components_failed=list(self.validation_rules.keys()),
                issues=issues,
            )

        # Validate each component
        for component, rules in self.validation_rules.items():
            logger.info(f"Validating component: {component}")

            component_issues = self._verify_component(component, rules)
            issues.extend(component_issues)

            # Check if component has any blocking errors
            blocking_errors = [
                issue
                for issue in component_issues
                if issue.severity
                in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]
            ]

            if blocking_errors:
                components_failed.append(component)
                logger.error(
                    f"Component {component} validation failed with {len(blocking_errors)} errors"
                )
            else:
                components_verified.append(component)
                logger.info(f"Component {component} validation passed")

        # Determine overall success
        has_blocking_issues = any(
            issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]
            for issue in issues
        )
        success = not has_blocking_issues

        result = PipelineValidationResult(
            success=success,
            components_verified=components_verified,
            components_failed=components_failed,
            issues=issues,
        )

        if success:
            logger.info("✅ Pipeline validation completed successfully")
        else:
            logger.error(f"❌ Pipeline validation failed with {len(issues)} issues")
            # Log summary by severity
            error_summary = result.get_errors_by_severity()
            for severity, errors in error_summary.items():
                if errors:
                    logger.error(f"  {severity.value}: {len(errors)} issues")

        return result

    def _verify_component(
        self, component: str, rules: list[ValidationRule]
    ) -> list[ValidationError]:
        """Verify a single pipeline component.

        Args:
            component: Name of the component to verify
            rules: List of validation rules to apply

        Returns:
            List of validation errors
        """
        logger.info(f"Verifying pipeline component: {component}")
        issues = []

        # First, check resource dependencies
        resource_issues = self.validate_resource_dependencies([component])
        issues.extend(resource_issues)

        # Run all validation rules
        context = {"component": component}
        for rule in rules:
            try:
                rule_issues = rule.validate(context)
                issues.extend(rule_issues)
            except Exception as e:
                issues.append(
                    ValidationErrorBuilder.module_import_failed(
                        component, rule.name, str(e)
                    )
                )

        return issues


if __name__ == "__main__":
    # Example usage
    validator = PipelineValidator()
    result = validator.validate()
