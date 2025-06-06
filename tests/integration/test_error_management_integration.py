"""
Integration tests for Error Management System - Feature 8: Fallback & Retry.

Tests the complete error management workflow including manual fix scripts,
bulk operations, and monitoring capabilities.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from leadfactory.pipeline.error_handling import ErrorCategory, ErrorSeverity, PipelineError
from leadfactory.pipeline.manual_fix_scripts import (
    DatabaseConnectionFix,
    NetworkTimeoutFix,
    ValidationErrorFix,
    manual_fix_orchestrator,
    FixResult
)
from leadfactory.monitoring.fix_script_monitoring import fix_script_monitor
from leadfactory.pipeline.error_aggregation import ErrorAggregator, TimeWindow


class TestErrorManagementIntegration:
    """Integration tests for the error management system."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_storage = MagicMock()
        self.error_aggregator = ErrorAggregator()

        # Configure mock storage
        self.mock_storage.test_connection.return_value = True
        self.mock_storage.close_idle_connections.return_value = None
        self.mock_storage.reset_connection_pool.return_value = None
        self.mock_storage.get_business.return_value = {
            'id': 123,
            'phone': '1234567890',
            'email': 'test@example.com',
            'website': 'example.com'
        }
        self.mock_storage.update_business.return_value = True
        self.mock_storage.dismiss_error.return_value = True
        self.mock_storage.update_error.return_value = True

    def test_database_connection_fix_end_to_end(self):
        """Test database connection fix from error to resolution."""
        # Create database connection error
        error = PipelineError(
            id="db_test_001",
            stage="scrape",
            operation="fetch_business_data",
            error_type="ConnectionTimeout",
            error_message="database connection timeout after 30 seconds",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE,
            business_id=123
        )

        # Apply fix script
        fix_script = DatabaseConnectionFix()
        with patch.object(fix_script, 'storage', self.mock_storage):
            execution = fix_script.fix_error(error)

        # Verify fix was successful
        assert execution.result == FixResult.SUCCESS
        assert execution.fix_id == "DatabaseConnectionFix"
        assert len(execution.changes_made) > 0
        assert "database connection" in execution.details.lower()

        # Verify storage methods were called
        self.mock_storage.close_idle_connections.assert_called_once()
        self.mock_storage.reset_connection_pool.assert_called_once()

    def test_validation_error_fix_with_data_update(self):
        """Test validation error fix that updates business data."""
        # Create validation error
        error = PipelineError(
            id="val_test_001",
            stage="enrich",
            operation="validate_business_data",
            error_type="ValidationError",
            error_message="invalid phone number format",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            business_id=123
        )

        # Apply fix script
        fix_script = ValidationErrorFix()
        with patch.object(fix_script, 'storage', self.mock_storage):
            execution = fix_script.fix_error(error)

        # Verify fix was successful
        assert execution.result == FixResult.SUCCESS
        assert any("phone number" in change.lower() for change in execution.changes_made)

        # Verify business data was updated
        self.mock_storage.get_business.assert_called_once_with(123)
        self.mock_storage.update_business.assert_called_once()

    def test_fix_orchestrator_multiple_applicable_scripts(self):
        """Test fix orchestrator with multiple applicable scripts."""
        # Create network error that could be handled by multiple scripts
        error = PipelineError(
            id="multi_test_001",
            stage="scrape",
            operation="fetch_data",
            error_type="NetworkTimeout",
            error_message="network timeout while accessing database",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NETWORK,
            business_id=124
        )

        # Get applicable fixes
        applicable_fixes = manual_fix_orchestrator.get_applicable_fixes(error)

        # Should find network timeout fix script
        assert len(applicable_fixes) > 0
        assert any(fix.fix_id == "NetworkTimeoutFix" for fix in applicable_fixes)

        # Apply fixes through orchestrator
        with patch.object(manual_fix_orchestrator, 'storage', self.mock_storage):
            executions = manual_fix_orchestrator.fix_error(error)

        # Should have at least one execution
        assert len(executions) > 0

        # Check if any execution was successful
        successful = any(ex.result == FixResult.SUCCESS for ex in executions)
        assert successful

    def test_error_aggregation_and_pattern_detection(self):
        """Test error aggregation and pattern detection."""
        # Create multiple similar errors
        errors = []
        for i in range(5):
            error = PipelineError(
                id=f"pattern_test_{i:03d}",
                stage="scrape",
                operation="fetch_url",
                error_type="ConnectionTimeout",
                error_message="connection timeout during scraping",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.NETWORK,
                business_id=200 + i
            )
            errors.append(error)
            self.error_aggregator.add_error(error)

        # Generate metrics
        metrics = self.error_aggregator.generate_error_metrics(TimeWindow.LAST_24_HOURS)

        # Verify pattern detection
        assert metrics.total_errors == 5
        assert len(metrics.patterns) > 0

        # Check top pattern
        top_pattern = metrics.patterns[0]
        assert top_pattern.error_type == "ConnectionTimeout"
        assert top_pattern.stage == "scrape"
        assert top_pattern.operation == "fetch_url"
        assert top_pattern.frequency == 5
        assert len(top_pattern.affected_businesses) == 5

    def test_fix_script_monitoring_and_alerts(self):
        """Test fix script monitoring and alert generation."""
        # Create fix script with execution history
        fix_script = DatabaseConnectionFix()

        # Add successful executions
        for i in range(3):
            from leadfactory.pipeline.manual_fix_scripts import FixExecution
            execution = FixExecution(
                fix_id="DatabaseConnectionFix",
                error_id=f"success_test_{i:03d}",
                business_id=123,
                timestamp=datetime.now() - timedelta(minutes=30 - i*10),
                result=FixResult.SUCCESS,
                duration_seconds=5.0 + i
            )
            fix_script.execution_history.append(execution)

        # Add failed executions
        for i in range(2):
            from leadfactory.pipeline.manual_fix_scripts import FixExecution
            execution = FixExecution(
                fix_id="DatabaseConnectionFix",
                error_id=f"failure_test_{i:03d}",
                business_id=124,
                timestamp=datetime.now() - timedelta(minutes=10 - i*5),
                result=FixResult.FAILED,
                duration_seconds=60.0 + i*10,  # Long duration
                errors_encountered=["Connection refused"]
            )
            fix_script.execution_history.append(execution)

        # Generate metrics
        metrics = fix_script_monitor.generate_script_metrics("DatabaseConnectionFix", hours=1)

        # Verify metrics
        assert metrics.total_executions == 5
        assert metrics.successful_executions == 3
        assert metrics.failed_executions == 2
        assert metrics.success_rate_percent == 60.0  # 3/5 * 100

        # Check alerts
        alerts = fix_script_monitor.check_fix_script_alerts(metrics)

        # Should have performance alert due to high average duration
        performance_alerts = [a for a in alerts if 'performance' in a.alert_type]
        assert len(performance_alerts) > 0

    def test_bulk_error_operations_workflow(self):
        """Test bulk error operations workflow."""
        # Create multiple errors
        errors = []
        error_ids = []

        for i in range(3):
            error_id = f"bulk_test_{i:03d}"
            error = PipelineError(
                id=error_id,
                stage="test_stage",
                operation="test_operation",
                error_type="TestError",
                error_message=f"Test error {i}",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.BUSINESS_LOGIC,
                business_id=300 + i
            )
            errors.append(error)
            error_ids.append(error_id)

        # Mock storage for bulk operations
        def mock_get_error(error_id):
            if error_id in error_ids:
                return {
                    'id': error_id,
                    'business_id': 300 + error_ids.index(error_id),
                    'category': 'business_logic',
                    'severity': 'medium'
                }
            return None

        self.mock_storage.get_error_by_id.side_effect = mock_get_error

        # Test bulk dismiss
        dismiss_result = self._simulate_bulk_dismiss(error_ids, "false_positive", "Test dismissal")

        assert len(dismiss_result['dismissed']) == 3
        assert len(dismiss_result['not_found']) == 0
        assert len(dismiss_result['failed']) == 0

        # Test bulk categorize
        categorize_result = self._simulate_bulk_categorize(
            error_ids,
            category="validation",
            severity="high",
            tags=["urgent", "investigate"]
        )

        assert len(categorize_result['updated']) == 3
        assert len(categorize_result['not_found']) == 0
        assert len(categorize_result['failed']) == 0

    def test_error_dashboard_data_generation(self):
        """Test error dashboard data generation."""
        # Add various errors to aggregator
        error_types = [
            ("critical_error", ErrorSeverity.CRITICAL),
            ("high_error", ErrorSeverity.HIGH),
            ("medium_error", ErrorSeverity.MEDIUM),
            ("low_error", ErrorSeverity.LOW)
        ]

        for i, (error_type, severity) in enumerate(error_types):
            error = PipelineError(
                id=f"dashboard_test_{i:03d}",
                stage="test_stage",
                operation="test_operation",
                error_type=error_type,
                error_message=f"Test {error_type}",
                severity=severity,
                category=ErrorCategory.BUSINESS_LOGIC,
                business_id=400 + i
            )
            self.error_aggregator.add_error(error)

        # Generate dashboard data
        metrics = self.error_aggregator.generate_error_metrics(TimeWindow.LAST_24_HOURS)
        alerts = self.error_aggregator.check_alert_thresholds(metrics)
        fix_stats = manual_fix_orchestrator.get_fix_script_stats()

        # Verify dashboard data
        assert metrics.total_errors == 4
        assert metrics.critical_error_count == 1
        assert len(metrics.affected_businesses) == 4

        # Verify fix script stats
        assert len(fix_stats) > 0
        assert all('description' in stats for stats in fix_stats.values())
        assert all('error_patterns' in stats for stats in fix_stats.values())

    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with retry mechanisms."""
        from leadfactory.pipeline.retry_mechanisms import CircuitBreaker, CircuitBreakerConfig

        # Create circuit breaker
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short timeout for testing
            success_threshold=2
        ))

        # Test failure accumulation
        assert circuit_breaker.can_execute()

        # Record failures
        for i in range(3):
            circuit_breaker.record_failure()

        # Circuit breaker should be open
        from leadfactory.pipeline.retry_mechanisms import CircuitBreakerState
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert not circuit_breaker.can_execute()

        # Wait for recovery timeout
        import time
        time.sleep(1.1)

        # Should transition to half-open
        assert circuit_breaker.can_execute()
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN

        # Record successful attempts
        circuit_breaker.record_success()
        circuit_breaker.record_success()

        # Should close
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.can_execute()

    def test_end_to_end_error_resolution_workflow(self):
        """Test complete end-to-end error resolution workflow."""
        # 1. Create error
        error = PipelineError(
            id="e2e_test_001",
            stage="scrape",
            operation="fetch_business_data",
            error_type="ConnectionTimeout",
            error_message="database connection timeout",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE,
            business_id=500
        )

        # 2. Add to aggregator for pattern tracking
        self.error_aggregator.add_error(error)

        # 3. Apply fix through orchestrator
        with patch.object(manual_fix_orchestrator, 'storage', self.mock_storage):
            fix_executions = manual_fix_orchestrator.fix_error(error)

        # 4. Verify fix was attempted and successful
        assert len(fix_executions) > 0
        successful_fix = any(ex.result == FixResult.SUCCESS for ex in fix_executions)
        assert successful_fix

        # 5. Generate monitoring report
        monitoring_report = fix_script_monitor.generate_monitoring_report(hours=1)

        # 6. Verify monitoring captured the fix
        assert monitoring_report['overall_statistics']['total_executions'] >= 1

        # 7. Check for any alerts
        assert 'active_alerts' in monitoring_report

        # 8. Verify error pattern was detected
        metrics = self.error_aggregator.generate_error_metrics(TimeWindow.LAST_HOUR)
        assert metrics.total_errors >= 1

    def _simulate_bulk_dismiss(self, error_ids, reason, comment):
        """Simulate bulk dismiss operation."""
        dismissed = []
        not_found = []
        failed = []

        for error_id in error_ids:
            error_data = self.mock_storage.get_error_by_id(error_id)
            if error_data:
                if self.mock_storage.dismiss_error(error_id, {
                    'reason': reason,
                    'comment': comment,
                    'dismissed_by': 'test_user'
                }):
                    dismissed.append({
                        'error_id': error_id,
                        'business_id': error_data['business_id']
                    })
                else:
                    failed.append(error_id)
            else:
                not_found.append(error_id)

        return {
            'dismissed': dismissed,
            'not_found': not_found,
            'failed': failed
        }

    def _simulate_bulk_categorize(self, error_ids, category=None, severity=None, tags=None):
        """Simulate bulk categorize operation."""
        updated = []
        not_found = []
        failed = []

        for error_id in error_ids:
            error_data = self.mock_storage.get_error_by_id(error_id)
            if error_data:
                update_data = {'updated_by': 'test_user'}
                if category:
                    update_data['category'] = category
                if severity:
                    update_data['severity'] = severity
                if tags:
                    update_data['tags'] = tags

                if self.mock_storage.update_error(error_id, update_data):
                    updated.append({
                        'error_id': error_id,
                        'business_id': error_data['business_id']
                    })
                else:
                    failed.append(error_id)
            else:
                not_found.append(error_id)

        return {
            'updated': updated,
            'not_found': not_found,
            'failed': failed
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
