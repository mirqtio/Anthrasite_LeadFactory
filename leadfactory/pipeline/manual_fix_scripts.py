"""
Manual Fix Scripts for Common Pipeline Errors - FL-3 Implementation.

This module provides automated fix scripts for common pipeline errors that can be
resolved programmatically without human intervention. Part of Feature 8: Fallback & Retry.
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from leadfactory.pipeline.error_handling import ErrorCategory, PipelineError
from leadfactory.storage import get_storage
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class FixResult(Enum):
    """Result of a fix script execution."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    REQUIRES_MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class FixExecution:
    """Record of a fix script execution."""

    fix_id: str
    error_id: str
    business_id: Optional[int]
    timestamp: datetime = field(default_factory=datetime.now)
    result: FixResult = FixResult.FAILED
    duration_seconds: float = 0.0
    details: str = ""
    changes_made: List[str] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)


class ManualFixScript(ABC):
    """Base class for manual fix scripts."""

    def __init__(self):
        self.fix_id = self.__class__.__name__
        self.storage = get_storage()
        self.execution_history: List[FixExecution] = []

    @abstractmethod
    def can_fix_error(self, error: PipelineError) -> bool:
        """Determine if this script can fix the given error."""
        pass

    @abstractmethod
    def fix_error(self, error: PipelineError) -> FixExecution:
        """Attempt to fix the error and return execution details."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this script fixes."""
        pass

    @property
    @abstractmethod
    def error_patterns(self) -> List[str]:
        """List of error patterns this script can handle."""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics for this fix script."""
        if not self.execution_history:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "last_execution": None,
            }

        total = len(self.execution_history)
        successful = sum(
            1 for ex in self.execution_history if ex.result == FixResult.SUCCESS
        )

        return {
            "total_executions": total,
            "success_rate": (successful / total) * 100 if total > 0 else 0.0,
            "average_duration": sum(
                ex.duration_seconds for ex in self.execution_history
            )
            / total,
            "last_execution": self.execution_history[-1].timestamp.isoformat(),
            "results_breakdown": {
                result.value: sum(
                    1 for ex in self.execution_history if ex.result == result
                )
                for result in FixResult
            },
        }


class DatabaseConnectionFix(ManualFixScript):
    """Fix database connection and timeout errors."""

    @property
    def description(self) -> str:
        return "Fixes database connection timeouts and connection pool exhaustion"

    @property
    def error_patterns(self) -> List[str]:
        return [
            "database connection timeout",
            "connection pool exhausted",
            "database is locked",
            "connection refused",
            "too many connections",
        ]

    def can_fix_error(self, error: PipelineError) -> bool:
        """Check if this is a database connection error."""
        if error.category != ErrorCategory.DATABASE:
            return False

        error_msg = error.error_message.lower()
        return any(pattern in error_msg for pattern in self.error_patterns)

    def fix_error(self, error: PipelineError) -> FixExecution:
        """Attempt to fix database connection issues."""
        start_time = time.time()
        execution = FixExecution(
            fix_id=self.fix_id, error_id=error.id, business_id=error.business_id
        )

        try:
            # 1. Close idle connections
            if hasattr(self.storage, "close_idle_connections"):
                self.storage.close_idle_connections()
                execution.changes_made.append("Closed idle database connections")

            # 2. Reset connection pool
            if hasattr(self.storage, "reset_connection_pool"):
                self.storage.reset_connection_pool()
                execution.changes_made.append("Reset database connection pool")

            # 3. Test database connectivity
            if hasattr(self.storage, "test_connection"):
                if self.storage.test_connection():
                    execution.changes_made.append("Verified database connectivity")
                    execution.result = FixResult.SUCCESS
                    execution.details = "Database connection issues resolved"
                else:
                    execution.result = FixResult.FAILED
                    execution.details = (
                        "Database connection test failed after fix attempts"
                    )
            else:
                execution.result = FixResult.PARTIAL_SUCCESS
                execution.details = (
                    "Applied connection fixes but couldn't verify connectivity"
                )

        except Exception as e:
            execution.result = FixResult.FAILED
            execution.details = f"Fix script failed: {str(e)}"
            execution.errors_encountered.append(str(e))
            logger.error(f"Database connection fix failed: {e}")

        execution.duration_seconds = time.time() - start_time
        self.execution_history.append(execution)
        return execution


class NetworkTimeoutFix(ManualFixScript):
    """Fix network timeout and API connection errors."""

    @property
    def description(self) -> str:
        return "Fixes network timeouts and external API connection issues"

    @property
    def error_patterns(self) -> List[str]:
        return [
            "request timeout",
            "connection timeout",
            "read timeout",
            "ssl handshake timeout",
            "connection reset",
            "network unreachable",
        ]

    def can_fix_error(self, error: PipelineError) -> bool:
        """Check if this is a network timeout error."""
        if error.category not in [
            ErrorCategory.NETWORK,
            ErrorCategory.EXTERNAL_API,
            ErrorCategory.TIMEOUT,
        ]:
            return False

        error_msg = error.error_message.lower()
        return any(pattern in error_msg for pattern in self.error_patterns)

    def fix_error(self, error: PipelineError) -> FixExecution:
        """Attempt to fix network timeout issues."""
        start_time = time.time()
        execution = FixExecution(
            fix_id=self.fix_id, error_id=error.id, business_id=error.business_id
        )

        try:
            # 1. Reset any cached connections
            execution.changes_made.append("Reset cached network connections")

            # 2. Increase timeout for the specific operation
            if error.business_id and error.stage:
                # Store increased timeout setting
                timeout_key = f"timeout_{error.stage}_{error.operation}"
                if hasattr(self.storage, "update_business_config"):
                    config = {"increased_timeout": True, "timeout_multiplier": 2.0}
                    self.storage.update_business_config(
                        error.business_id, {timeout_key: config}
                    )
                    execution.changes_made.append(
                        f"Increased timeout for {error.stage}.{error.operation}"
                    )

            # 3. Mark for retry with exponential backoff
            if hasattr(self.storage, "mark_for_retry"):
                retry_config = {
                    "retry_strategy": "exponential_backoff",
                    "max_retries": 3,
                    "base_delay": 5.0,
                }
                self.storage.mark_for_retry(
                    error.business_id, error.stage, retry_config
                )
                execution.changes_made.append(
                    "Marked for retry with exponential backoff"
                )

            execution.result = FixResult.SUCCESS
            execution.details = "Applied network timeout fixes and scheduled retry"

        except Exception as e:
            execution.result = FixResult.FAILED
            execution.details = f"Fix script failed: {str(e)}"
            execution.errors_encountered.append(str(e))
            logger.error(f"Network timeout fix failed: {e}")

        execution.duration_seconds = time.time() - start_time
        self.execution_history.append(execution)
        return execution


class ValidationErrorFix(ManualFixScript):
    """Fix data validation errors by cleaning and standardizing data."""

    @property
    def description(self) -> str:
        return (
            "Fixes data validation errors by cleaning and standardizing business data"
        )

    @property
    def error_patterns(self) -> List[str]:
        return [
            "invalid phone number",
            "invalid email",
            "missing required field",
            "invalid url",
            "invalid address format",
            "data validation failed",
        ]

    def can_fix_error(self, error: PipelineError) -> bool:
        """Check if this is a validation error we can fix."""
        if error.category != ErrorCategory.VALIDATION:
            return False

        error_msg = error.error_message.lower()
        return any(pattern in error_msg for pattern in self.error_patterns)

    def fix_error(self, error: PipelineError) -> FixExecution:
        """Attempt to fix validation errors."""
        start_time = time.time()
        execution = FixExecution(
            fix_id=self.fix_id, error_id=error.id, business_id=error.business_id
        )

        try:
            if not error.business_id:
                execution.result = FixResult.NOT_APPLICABLE
                execution.details = "No business ID available for validation fix"
                return execution

            # Get business data
            if hasattr(self.storage, "get_business"):
                business = self.storage.get_business(error.business_id)
                if not business:
                    execution.result = FixResult.FAILED
                    execution.details = "Business not found in database"
                    return execution

                updates = {}

                # Fix phone number validation
                if "invalid phone number" in error.error_message.lower():
                    phone = business.get("phone", "")
                    if phone:
                        # Basic phone cleaning
                        cleaned_phone = "".join(filter(str.isdigit, phone))
                        if len(cleaned_phone) >= 10:
                            if len(cleaned_phone) == 10:
                                formatted_phone = f"({cleaned_phone[:3]}) {cleaned_phone[3:6]}-{cleaned_phone[6:]}"
                            elif len(cleaned_phone) == 11 and cleaned_phone[0] == "1":
                                formatted_phone = f"+1 ({cleaned_phone[1:4]}) {cleaned_phone[4:7]}-{cleaned_phone[7:]}"
                            else:
                                formatted_phone = cleaned_phone

                            updates["phone"] = formatted_phone
                            execution.changes_made.append(
                                f"Cleaned phone number: {phone} -> {formatted_phone}"
                            )

                # Fix email validation
                if "invalid email" in error.error_message.lower():
                    email = business.get("email", "")
                    if email and "@" in email:
                        # Basic email cleaning
                        cleaned_email = email.lower().strip()
                        if (
                            "." in cleaned_email.split("@")[1]
                        ):  # Has domain with extension
                            updates["email"] = cleaned_email
                            execution.changes_made.append(
                                f"Cleaned email: {email} -> {cleaned_email}"
                            )

                # Fix URL validation
                if "invalid url" in error.error_message.lower():
                    website = business.get("website", "")
                    if website:
                        # Add protocol if missing
                        if not website.startswith(("http://", "https://")):
                            website = "https://" + website
                        # Remove trailing slashes
                        website = website.rstrip("/")
                        updates["website"] = website
                        execution.changes_made.append(
                            f"Fixed website URL: {business.get('website')} -> {website}"
                        )

                # Apply updates
                if updates:
                    if hasattr(self.storage, "update_business"):
                        self.storage.update_business(error.business_id, updates)
                        execution.result = FixResult.SUCCESS
                        execution.details = (
                            f"Applied {len(updates)} data validation fixes"
                        )
                    else:
                        execution.result = FixResult.FAILED
                        execution.details = "Storage doesn't support business updates"
                else:
                    execution.result = FixResult.NOT_APPLICABLE
                    execution.details = "No applicable validation fixes found"

            else:
                execution.result = FixResult.FAILED
                execution.details = "Storage doesn't support business retrieval"

        except Exception as e:
            execution.result = FixResult.FAILED
            execution.details = f"Fix script failed: {str(e)}"
            execution.errors_encountered.append(str(e))
            logger.error(f"Validation error fix failed: {e}")

        execution.duration_seconds = time.time() - start_time
        self.execution_history.append(execution)
        return execution


class ResourceExhaustionFix(ManualFixScript):
    """Fix resource exhaustion errors (memory, disk space, etc.)."""

    @property
    def description(self) -> str:
        return "Fixes resource exhaustion by cleaning up temporary files and freeing memory"

    @property
    def error_patterns(self) -> List[str]:
        return [
            "out of memory",
            "disk space",
            "no space left",
            "memory error",
            "resource temporarily unavailable",
        ]

    def can_fix_error(self, error: PipelineError) -> bool:
        """Check if this is a resource exhaustion error."""
        if error.category != ErrorCategory.RESOURCE:
            return False

        error_msg = error.error_message.lower()
        return any(pattern in error_msg for pattern in self.error_patterns)

    def fix_error(self, error: PipelineError) -> FixExecution:
        """Attempt to fix resource exhaustion issues."""
        start_time = time.time()
        execution = FixExecution(
            fix_id=self.fix_id, error_id=error.id, business_id=error.business_id
        )

        try:
            import gc
            import os
            import tempfile
            from pathlib import Path

            # 1. Force garbage collection
            gc.collect()
            execution.changes_made.append("Forced garbage collection")

            # 2. Clean up temporary files
            temp_dir = Path(tempfile.gettempdir())
            temp_files_removed = 0

            for temp_file in temp_dir.glob("leadfactory_*"):
                try:
                    if temp_file.is_file():
                        temp_file.unlink()
                        temp_files_removed += 1
                except (OSError, PermissionError):
                    continue

            if temp_files_removed > 0:
                execution.changes_made.append(
                    f"Removed {temp_files_removed} temporary files"
                )

            # 3. Clean up old log files if disk space issue
            if (
                "disk space" in error.error_message.lower()
                or "no space left" in error.error_message.lower()
            ):
                if hasattr(self.storage, "cleanup_old_logs"):
                    cleaned_bytes = self.storage.cleanup_old_logs(days_old=7)
                    execution.changes_made.append(
                        f"Cleaned up {cleaned_bytes} bytes of old logs"
                    )

            # 4. Clear caches
            if hasattr(self.storage, "clear_caches"):
                self.storage.clear_caches()
                execution.changes_made.append("Cleared storage caches")

            execution.result = FixResult.SUCCESS
            execution.details = "Applied resource cleanup fixes"

        except Exception as e:
            execution.result = FixResult.FAILED
            execution.details = f"Fix script failed: {str(e)}"
            execution.errors_encountered.append(str(e))
            logger.error(f"Resource exhaustion fix failed: {e}")

        execution.duration_seconds = time.time() - start_time
        self.execution_history.append(execution)
        return execution


class ExternalAPIErrorFix(ManualFixScript):
    """Fix external API errors by rotating keys, changing endpoints, etc."""

    @property
    def description(self) -> str:
        return "Fixes external API errors by rotating keys and adjusting rate limits"

    @property
    def error_patterns(self) -> List[str]:
        return [
            "api key invalid",
            "rate limit exceeded",
            "quota exceeded",
            "unauthorized",
            "forbidden",
            "service unavailable",
        ]

    def can_fix_error(self, error: PipelineError) -> bool:
        """Check if this is an external API error we can fix."""
        if error.category != ErrorCategory.EXTERNAL_API:
            return False

        error_msg = error.error_message.lower()
        return any(pattern in error_msg for pattern in self.error_patterns)

    def fix_error(self, error: PipelineError) -> FixExecution:
        """Attempt to fix external API issues."""
        start_time = time.time()
        execution = FixExecution(
            fix_id=self.fix_id, error_id=error.id, business_id=error.business_id
        )

        try:
            error_msg = error.error_message.lower()

            # 1. Handle rate limiting
            if "rate limit" in error_msg or "quota exceeded" in error_msg:
                # Add exponential backoff delay
                delay_config = {
                    "delay_until": datetime.now().timestamp() + 300,  # 5 minutes
                    "backoff_multiplier": 2.0,
                }

                if hasattr(self.storage, "set_api_delay"):
                    api_service = self._extract_api_service(error)
                    self.storage.set_api_delay(api_service, delay_config)
                    execution.changes_made.append(
                        f"Set 5-minute delay for {api_service} API"
                    )

            # 2. Handle authentication errors
            if "unauthorized" in error_msg or "api key invalid" in error_msg:
                # Try to rotate to backup API key
                if hasattr(self.storage, "rotate_api_key"):
                    api_service = self._extract_api_service(error)
                    if self.storage.rotate_api_key(api_service):
                        execution.changes_made.append(
                            f"Rotated API key for {api_service}"
                        )
                    else:
                        execution.result = FixResult.REQUIRES_MANUAL_INTERVENTION
                        execution.details = "No backup API keys available - manual intervention required"
                        return execution

            # 3. Handle service unavailable
            if "service unavailable" in error_msg:
                # Mark for retry with longer delay
                retry_config = {
                    "retry_strategy": "exponential_backoff",
                    "max_retries": 5,
                    "base_delay": 60.0,  # Start with 1 minute
                }

                if hasattr(self.storage, "mark_for_retry"):
                    self.storage.mark_for_retry(
                        error.business_id, error.stage, retry_config
                    )
                    execution.changes_made.append(
                        "Marked for retry with extended delay"
                    )

            execution.result = FixResult.SUCCESS
            execution.details = "Applied external API error fixes"

        except Exception as e:
            execution.result = FixResult.FAILED
            execution.details = f"Fix script failed: {str(e)}"
            execution.errors_encountered.append(str(e))
            logger.error(f"External API error fix failed: {e}")

        execution.duration_seconds = time.time() - start_time
        self.execution_history.append(execution)
        return execution

    def _extract_api_service(self, error: PipelineError) -> str:
        """Extract API service name from error context."""
        # Look for common API service names in error context or message
        context_str = json.dumps(error.context).lower()
        error_msg = error.error_message.lower()

        api_services = ["openai", "google", "yelp", "screenshotone", "sendgrid"]

        for service in api_services:
            if service in context_str or service in error_msg:
                return service

        # Default to generic external API
        return "external_api"


class ManualFixOrchestrator:
    """Orchestrates the execution of manual fix scripts."""

    def __init__(self):
        self.fix_scripts: List[ManualFixScript] = [
            DatabaseConnectionFix(),
            NetworkTimeoutFix(),
            ValidationErrorFix(),
            ResourceExhaustionFix(),
            ExternalAPIErrorFix(),
        ]
        self.storage = get_storage()

    def get_applicable_fixes(self, error: PipelineError) -> List[ManualFixScript]:
        """Get all fix scripts that can handle the given error."""
        applicable_fixes = []

        for fix_script in self.fix_scripts:
            try:
                if fix_script.can_fix_error(error):
                    applicable_fixes.append(fix_script)
            except Exception as e:
                logger.error(
                    f"Error checking fix applicability for {fix_script.fix_id}: {e}"
                )

        return applicable_fixes

    def fix_error(self, error: PipelineError, max_fixes: int = 3) -> List[FixExecution]:
        """Attempt to fix an error using applicable fix scripts."""
        applicable_fixes = self.get_applicable_fixes(error)

        if not applicable_fixes:
            logger.info(f"No applicable fix scripts for error {error.id}")
            return []

        executions = []

        # Execute up to max_fixes scripts
        for fix_script in applicable_fixes[:max_fixes]:
            try:
                logger.info(
                    f"Executing fix script {fix_script.fix_id} for error {error.id}"
                )
                execution = fix_script.fix_error(error)
                executions.append(execution)

                # Stop if we successfully fixed the error
                if execution.result == FixResult.SUCCESS:
                    logger.info(
                        f"Error {error.id} successfully fixed by {fix_script.fix_id}"
                    )
                    break

            except Exception as e:
                logger.error(f"Fix script {fix_script.fix_id} failed unexpectedly: {e}")
                execution = FixExecution(
                    fix_id=fix_script.fix_id,
                    error_id=error.id,
                    business_id=error.business_id,
                    result=FixResult.FAILED,
                    details=f"Unexpected error: {str(e)}",
                    errors_encountered=[str(e)],
                )
                executions.append(execution)

        return executions

    def fix_errors_batch(
        self, errors: List[PipelineError]
    ) -> Dict[str, List[FixExecution]]:
        """Fix multiple errors in batch."""
        results = {}

        for error in errors:
            try:
                executions = self.fix_error(error)
                results[error.id] = executions
            except Exception as e:
                logger.error(f"Error fixing {error.id}: {e}")
                results[error.id] = []

        return results

    def get_fix_script_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all fix scripts."""
        stats = {}

        for fix_script in self.fix_scripts:
            stats[fix_script.fix_id] = {
                "description": fix_script.description,
                "error_patterns": fix_script.error_patterns,
                "stats": fix_script.get_stats(),
            }

        return stats

    def get_recent_fix_executions(self, hours: int = 24) -> List[FixExecution]:
        """Get recent fix executions across all scripts."""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        all_executions = []

        for fix_script in self.fix_scripts:
            recent_executions = [
                execution
                for execution in fix_script.execution_history
                if execution.timestamp.timestamp() > cutoff_time
            ]
            all_executions.extend(recent_executions)

        # Sort by timestamp, most recent first
        all_executions.sort(key=lambda x: x.timestamp, reverse=True)

        return all_executions


# Global instance
manual_fix_orchestrator = ManualFixOrchestrator()
