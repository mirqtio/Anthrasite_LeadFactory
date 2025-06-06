"""
A/B Test Notification Service - Automated notifications for test lifecycle events.

Implements automated monitoring and notification for A/B test events:
- Test completion detection
- Statistical significance alerts
- Automated report generation and distribution
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from leadfactory.ab_testing.ab_test_manager import ABTestManager, TestStatus
from leadfactory.ab_testing.report_generator import ABTestReportGenerator
from leadfactory.ab_testing.statistical_engine import StatisticalEngine
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ABTestNotificationService:
    """Service for managing A/B test notifications and automated workflows."""

    def __init__(self):
        """Initialize the notification service."""
        self.ab_manager = ABTestManager()
        self.report_generator = ABTestReportGenerator()
        self.stats_engine = StatisticalEngine()
        self.notification_config = self._load_notification_config()

    def _load_notification_config(self) -> Dict[str, Any]:
        """Load notification configuration."""
        # Default configuration
        default_config = {
            "auto_report_on_completion": True,
            "auto_report_on_significance": True,
            "default_recipients": ["data-team@company.com", "marketing@company.com"],
            "significance_check_interval_hours": 6,
            "completion_check_interval_hours": 1,
            "early_stopping_enabled": True,
            "early_stopping_confidence": 0.99,
        }

        try:
            # Try to load from config file if it exists
            with open("config/ab_testing_notifications.json", "r") as f:
                config = json.load(f)
                return {**default_config, **config}
        except FileNotFoundError:
            logger.info("Using default A/B testing notification configuration")
            return default_config

    def check_for_completed_tests(self) -> List[str]:
        """Check for tests that have reached their end date and should be completed.

        Returns:
            List of test IDs that were completed
        """
        completed_tests = []

        try:
            # Get all active tests
            active_tests = self.ab_manager.get_active_tests()
            current_time = datetime.utcnow()

            for test in active_tests:
                # Check if test has reached end date
                if test.end_date and current_time >= test.end_date:
                    logger.info(f"Auto-completing test {test.id} - end date reached")

                    # Stop the test
                    self.ab_manager.stop_test(test.id)
                    completed_tests.append(test.id)

                    # Generate and send report if configured
                    if self.notification_config.get("auto_report_on_completion", True):
                        self._send_completion_report(test.id)

                # Check for early completion based on sample size
                elif self._should_complete_early(test):
                    logger.info(
                        f"Auto-completing test {test.id} - target sample size reached"
                    )

                    # Stop the test
                    self.ab_manager.stop_test(test.id)
                    completed_tests.append(test.id)

                    # Generate and send report
                    if self.notification_config.get("auto_report_on_completion", True):
                        self._send_completion_report(test.id)

            if completed_tests:
                logger.info(f"Auto-completed {len(completed_tests)} A/B tests")

            return completed_tests

        except Exception as e:
            logger.error(f"Error checking for completed tests: {e}")
            return []

    def check_for_significant_results(self) -> List[Dict[str, Any]]:
        """Check active tests for statistical significance.

        Returns:
            List of tests with significant results
        """
        significant_tests = []

        try:
            # Get all active tests
            active_tests = self.ab_manager.get_active_tests()

            for test in active_tests:
                # Skip tests that are too new (need minimum sample)
                if not self._has_minimum_sample_size(test):
                    continue

                # Get test results and run statistical analysis
                test_results = self.ab_manager.get_test_results(test.id)
                stats_results = self.stats_engine.analyze_test_results(test_results)

                p_value = stats_results.get("p_value", 1.0)

                # Check for statistical significance
                if p_value < test.significance_threshold:
                    significant_result = {
                        "test_id": test.id,
                        "test_name": test.name,
                        "p_value": p_value,
                        "recommended_variant": stats_results.get("recommended_variant"),
                        "effect_size": stats_results.get("effect_size", 0.0),
                        "confidence_level": (1 - test.significance_threshold) * 100,
                    }

                    significant_tests.append(significant_result)

                    logger.info(
                        f"Test {test.id} shows significant results (p={p_value:.4f})"
                    )

                    # Send significance alert if configured
                    if self.notification_config.get(
                        "auto_report_on_significance", True
                    ):
                        self._send_significance_alert(test.id, significant_result)

                    # Early stopping if enabled and high confidence
                    if self.notification_config.get(
                        "early_stopping_enabled", True
                    ) and p_value < (
                        1
                        - self.notification_config.get(
                            "early_stopping_confidence", 0.99
                        )
                    ):

                        logger.info(
                            f"Early stopping test {test.id} due to high confidence"
                        )
                        self.ab_manager.stop_test(test.id)
                        self._send_completion_report(test.id, early_stop=True)

            return significant_tests

        except Exception as e:
            logger.error(f"Error checking for significant results: {e}")
            return []

    def _should_complete_early(self, test) -> bool:
        """Check if test should be completed early based on sample size."""
        try:
            test_results = self.ab_manager.get_test_results(test.id)
            total_participants = test_results.get("total_assignments", 0)

            # Complete if we've reached target sample size
            return total_participants >= test.target_sample_size

        except Exception as e:
            logger.error(f"Error checking early completion for test {test.id}: {e}")
            return False

    def _has_minimum_sample_size(self, test) -> bool:
        """Check if test has minimum sample size for statistical analysis."""
        try:
            test_results = self.ab_manager.get_test_results(test.id)
            total_participants = test_results.get("total_assignments", 0)

            # Need at least 100 participants per variant for meaningful analysis
            min_per_variant = 100
            min_total = min_per_variant * len(test.variants)

            return total_participants >= min_total

        except Exception as e:
            logger.error(f"Error checking minimum sample size for test {test.id}: {e}")
            return False

    def _send_completion_report(self, test_id: str, early_stop: bool = False):
        """Send completion report for a test."""
        try:
            # Get recipient list
            recipients = self._get_notification_recipients(test_id)

            if not recipients:
                logger.warning(
                    f"No recipients configured for test {test_id} completion report"
                )
                return

            # Generate and send report
            report_bytes = self.report_generator.generate_test_end_report(
                test_id, auto_email=True, recipient_emails=recipients
            )

            # Log the completion
            stop_reason = (
                "early stopping due to significance"
                if early_stop
                else "scheduled completion"
            )
            logger.info(
                f"Sent completion report for test {test_id} ({stop_reason}) to {len(recipients)} recipients"
            )

        except Exception as e:
            logger.error(f"Error sending completion report for test {test_id}: {e}")

    def _send_significance_alert(
        self, test_id: str, significant_result: Dict[str, Any]
    ):
        """Send alert for statistically significant results."""
        try:
            import asyncio
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            recipients = self._get_notification_recipients(test_id)

            if not recipients:
                logger.warning(
                    f"No recipients configured for test {test_id} significance alert"
                )
                return

            # Prepare alert email
            subject = f"🎯 A/B Test Alert: Significant Results Detected - {significant_result['test_name']}"

            body = f"""
            Statistical significance detected in your A/B test!

            Test: {significant_result['test_name']}
            Test ID: {test_id}

            📊 Results Summary:
            • P-value: {significant_result['p_value']:.4f}
            • Confidence Level: {significant_result['confidence_level']:.1f}%
            • Recommended Variant: {significant_result['recommended_variant']}
            • Effect Size: {significant_result['effect_size']:.4f}

            The test is showing statistically significant results. Consider reviewing the data and deciding whether to:
            1. Continue running the test to completion
            2. Stop early and implement the winning variant
            3. Extend the test duration for additional validation

            A detailed report will be sent when the test completes.

            Best regards,
            LeadFactory A/B Testing Team
            """

            # Send alert emails
            for email in recipients:
                self._send_simple_email(email, subject, body)

            logger.info(
                f"Sent significance alert for test {test_id} to {len(recipients)} recipients"
            )

        except Exception as e:
            logger.error(f"Error sending significance alert for test {test_id}: {e}")

    def _get_notification_recipients(self, test_id: str) -> List[str]:
        """Get notification recipients for a test."""
        try:
            # Get test-specific recipients from metadata
            test_config = self.ab_manager.get_test_config(test_id)
            if test_config and test_config.metadata:
                test_recipients = test_config.metadata.get(
                    "notification_recipients", []
                )
                if test_recipients:
                    return test_recipients

            # Fall back to default recipients
            return self.notification_config.get("default_recipients", [])

        except Exception as e:
            logger.error(
                f"Error getting notification recipients for test {test_id}: {e}"
            )
            return self.notification_config.get("default_recipients", [])

    def run_periodic_checks(self):
        """Run all periodic checks for A/B test monitoring."""
        logger.info("Running periodic A/B test checks")

        # Check for completed tests
        completed_tests = self.check_for_completed_tests()

        # Check for significant results
        significant_tests = self.check_for_significant_results()

        # Return summary
        return {
            "completed_tests": len(completed_tests),
            "significant_tests": len(significant_tests),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def schedule_test_completion_check(
        self, test_id: str, check_time: datetime, recipients: Optional[List[str]] = None
    ):
        """Schedule a specific completion check for a test.

        Args:
            test_id: Test identifier
            check_time: When to check for completion
            recipients: Optional list of email recipients
        """
        try:
            # Store the scheduled check (in a real implementation, this would use a job queue)
            scheduled_check = {
                "test_id": test_id,
                "check_time": check_time.isoformat(),
                "recipients": recipients or self._get_notification_recipients(test_id),
                "type": "completion_check",
            }

            # In a production system, this would be stored in a database or job queue
            logger.info(
                f"Scheduled completion check for test {test_id} at {check_time}"
            )

        except Exception as e:
            logger.error(f"Error scheduling completion check for test {test_id}: {e}")

    def get_notification_status(self, test_id: str) -> Dict[str, Any]:
        """Get notification status for a test.

        Args:
            test_id: Test identifier

        Returns:
            Dictionary with notification status information
        """
        try:
            test_config = self.ab_manager.get_test_config(test_id)
            if not test_config:
                return {"error": "Test not found"}

            test_results = self.ab_manager.get_test_results(test_id)
            stats_results = self.stats_engine.analyze_test_results(test_results)

            return {
                "test_id": test_id,
                "test_name": test_config.name,
                "status": test_config.status.value,
                "auto_report_enabled": self.notification_config.get(
                    "auto_report_on_completion", True
                ),
                "significance_monitoring": self.notification_config.get(
                    "auto_report_on_significance", True
                ),
                "recipients": self._get_notification_recipients(test_id),
                "current_p_value": stats_results.get("p_value", 1.0),
                "is_significant": stats_results.get("p_value", 1.0)
                < test_config.significance_threshold,
                "total_participants": test_results.get("total_assignments", 0),
                "target_sample_size": test_config.target_sample_size,
                "completion_progress": min(
                    1.0,
                    test_results.get("total_assignments", 0)
                    / test_config.target_sample_size,
                ),
            }

        except Exception as e:
            logger.error(f"Error getting notification status for test {test_id}: {e}")
            return {"error": str(e)}

    def _send_simple_email(self, to_email: str, subject: str, body: str):
        """Send a simple email notification (mock implementation for testing)."""
        try:
            # In a real implementation, this would use the email service
            # For now, just log the email attempt
            logger.info(f"Would send email to {to_email}: {subject}")
            logger.debug(f"Email body preview: {body[:100]}...")
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")


# Global instance
notification_service = ABTestNotificationService()
