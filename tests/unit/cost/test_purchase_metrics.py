"""
Unit tests for purchase metrics tracking functionality.
"""

import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from leadfactory.cost.purchase_metrics import PurchaseMetricsTracker


class TestPurchaseMetricsTracker:
    """Test suite for purchase metrics tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()

        # Mock financial tracker
        self.mock_financial_tracker = Mock()
        self.mock_financial_tracker.record_stripe_payment.return_value = "txn_test_123"
        self.mock_financial_tracker.record_stripe_refund.return_value = "refund_test_123"

        # Create tracker instance with mocked dependencies
        self.tracker = PurchaseMetricsTracker(financial_tracker=self.mock_financial_tracker)

    def teardown_method(self):
        """Clean up test fixtures."""
        import os
        try:
            os.unlink(self.temp_db.name)
        except FileNotFoundError:
            pass

    def test_record_purchase_basic(self):
        """Test basic purchase recording functionality."""
        # Test data
        purchase_data = {
            "stripe_payment_intent_id": "pi_test_12345",
            "stripe_charge_id": "ch_test_12345",
            "customer_email": "test@example.com",
            "customer_name": "Test Customer",
            "gross_amount_cents": 2999,  # $29.99
            "net_amount_cents": 2850,    # After fees
            "stripe_fee_cents": 149,     # ~5% fee
            "audit_type": "basic",
            "currency": "usd",
            "metadata": {"source": "test"},
        }

        # Mock metrics recording
        with patch("leadfactory.cost.purchase_metrics.record_metric") as mock_record_metric:
            transaction_id = self.tracker.record_purchase(**purchase_data)

            # Verify financial tracker was called
            self.mock_financial_tracker.record_stripe_payment.assert_called_once_with(
                stripe_payment_intent_id="pi_test_12345",
                stripe_charge_id="ch_test_12345",
                customer_email="test@example.com",
                customer_name="Test Customer",
                gross_amount_cents=2999,
                net_amount_cents=2850,
                stripe_fee_cents=149,
                audit_type="basic",
                currency="usd",
                metadata={"source": "test"},
            )

            # Verify metrics were recorded
            assert mock_record_metric.called

            # Verify transaction ID returned
            assert transaction_id == "txn_test_123"

    def test_record_refund_basic(self):
        """Test basic refund recording functionality."""
        refund_data = {
            "stripe_payment_intent_id": "pi_test_12345",
            "stripe_charge_id": "ch_test_12345",
            "refund_amount_cents": 2999,
            "reason": "requested_by_customer",
            "currency": "usd",
            "metadata": {"refund_id": "re_test_123"},
        }

        # Mock metrics recording
        with patch("leadfactory.cost.purchase_metrics.record_metric") as mock_record_metric:
            transaction_id = self.tracker.record_refund(**refund_data)

            # Verify financial tracker was called
            self.mock_financial_tracker.record_stripe_refund.assert_called_once_with(
                stripe_payment_intent_id="pi_test_12345",
                stripe_charge_id="ch_test_12345",
                refund_amount_cents=2999,
                reason="requested_by_customer",
                metadata={"refund_id": "re_test_123"},
            )

            # Verify refund metrics were recorded
            assert mock_record_metric.called

            # Verify transaction ID returned
            assert transaction_id == "refund_test_123"

    def test_get_conversion_metrics(self):
        """Test conversion metrics calculation."""
        # Mock monthly summary data
        mock_monthly_summary = {
            "total_transactions": 25,
            "total_revenue_cents": 74975,  # $749.75
            "total_refunds": 2,
            "total_refund_amount_cents": 5998,  # $59.98
        }

        self.mock_financial_tracker.get_monthly_summary.return_value = mock_monthly_summary

        with patch("leadfactory.cost.purchase_metrics.record_metric") as mock_record_metric:
            conversion_data = self.tracker.get_conversion_metrics("basic")

            # Verify structure
            assert "period" in conversion_data
            assert "audit_type" in conversion_data
            assert "metrics" in conversion_data

            # Verify calculated metrics
            metrics = conversion_data["metrics"]
            assert metrics["total_purchases"] == 25
            assert metrics["total_revenue_cents"] == 74975
            assert metrics["average_order_value_cents"] == 74975 // 25  # $29.99

            # Verify metrics were recorded
            assert mock_record_metric.called

    def test_get_customer_lifetime_value(self):
        """Test customer lifetime value calculation."""
        # Mock profit data
        mock_profit_data = {
            "revenue": {"net_revenue_dollars": 1500.0},
            "costs": {"total_costs_dollars": 200.0},
            "profit": {"gross_profit_dollars": 1300.0},
        }

        mock_monthly_summary = {
            "total_transactions": 50,
        }

        self.mock_financial_tracker.get_profit_margin_data.return_value = mock_profit_data
        self.mock_financial_tracker.get_monthly_summary.return_value = mock_monthly_summary

        with patch("leadfactory.cost.purchase_metrics.record_metric") as mock_record_metric:
            clv = self.tracker.get_customer_lifetime_value(365)

            # Verify CLV calculation
            # $1500 revenue / (50 transactions / 2 estimated customers) = $60 CLV
            expected_clv = 1500.0 / 25  # $60 per customer
            assert abs(clv - expected_clv) < 1.0  # Allow small rounding differences

            # Verify CLV metric was recorded
            assert mock_record_metric.called

    def test_get_purchase_analytics_summary(self):
        """Test comprehensive analytics summary generation."""
        # Mock all required data
        today = datetime.now().strftime("%Y-%m-%d")

        mock_daily_summary = {
            "date": today,
            "total_revenue_cents": 5998,  # $59.98
            "transaction_count": 2,
            "total_stripe_fees_cents": 204,  # $2.04
            "net_revenue_cents": 5794,  # $57.94
            "refund_count": 0,
            "refund_amount_cents": 0,
        }

        mock_monthly_summary = {
            "year": 2024,
            "month": 6,
            "total_revenue_cents": 149950,  # $1,499.50
            "total_transactions": 50,
            "active_days": 15,
            "total_refunds": 3,
            "total_refund_amount_cents": 8997,  # $89.97
        }

        mock_profit_data = {
            "period": {"start_date": "2024-05-05", "end_date": "2024-06-04"},
            "revenue": {
                "gross_revenue_dollars": 1499.50,
                "stripe_fees_dollars": 51.98,
                "net_revenue_dollars": 1447.52,
            },
            "costs": {"total_costs_dollars": 150.00},
            "profit": {
                "gross_profit_dollars": 1297.52,
                "gross_margin_percent": 89.6,
            },
        }

        self.mock_financial_tracker.get_daily_summary.return_value = mock_daily_summary
        self.mock_financial_tracker.get_monthly_summary.return_value = mock_monthly_summary
        self.mock_financial_tracker.get_profit_margin_data.return_value = mock_profit_data

        # Mock CLV calculation
        with patch.object(self.tracker, 'get_customer_lifetime_value', return_value=120.50) as mock_clv, \
             patch.object(self.tracker, 'get_conversion_metrics', return_value={"test": "data"}) as mock_conversion:

            summary = self.tracker.get_purchase_analytics_summary()

            # Verify structure
            assert "timestamp" in summary
            assert "daily_metrics" in summary
            assert "monthly_metrics" in summary
            assert "profit_analysis" in summary
            assert "customer_metrics" in summary
            assert "conversion_metrics" in summary

            # Verify data inclusion
            assert summary["daily_metrics"] == mock_daily_summary
            assert summary["monthly_metrics"] == mock_monthly_summary
            assert summary["profit_analysis"] == mock_profit_data
            assert summary["customer_metrics"]["lifetime_value_dollars"] == 120.50

            # Verify methods were called
            mock_clv.assert_called_once()
            mock_conversion.assert_called_once()

    def test_update_aggregated_metrics(self):
        """Test aggregated metrics updating."""
        # Mock daily summary
        today = datetime.now().strftime("%Y-%m-%d")
        mock_daily_summary = {
            "total_revenue_cents": 5998,
        }

        mock_monthly_summary = {
            "total_revenue_cents": 149950,
        }

        self.mock_financial_tracker.get_daily_summary.return_value = mock_daily_summary
        self.mock_financial_tracker.get_monthly_summary.return_value = mock_monthly_summary

        with patch("leadfactory.cost.purchase_metrics.record_metric") as mock_record_metric:
            # Call internal method directly
            self.tracker._update_aggregated_metrics()

            # Verify metrics were recorded
            assert mock_record_metric.called

    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test with financial tracker that raises an exception
        self.mock_financial_tracker.record_stripe_payment.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            self.tracker.record_purchase(
                stripe_payment_intent_id="pi_test_error",
                stripe_charge_id="ch_test_error",
                customer_email="error@example.com",
                customer_name="Error Test",
                gross_amount_cents=1000,
                net_amount_cents=950,
                stripe_fee_cents=50,
                audit_type="basic",
            )

        # Test analytics summary with missing data
        self.mock_financial_tracker.get_daily_summary.return_value = None
        self.mock_financial_tracker.get_monthly_summary.side_effect = Exception("Data error")

        summary = self.tracker.get_purchase_analytics_summary()

        # Should still return a summary with error information
        assert "error" in summary
        assert "timestamp" in summary

    def test_metrics_recording_with_labels(self):
        """Test that metrics are recorded with proper labels."""
        purchase_data = {
            "stripe_payment_intent_id": "pi_test_labels",
            "stripe_charge_id": "ch_test_labels",
            "customer_email": "labels@example.com",
            "customer_name": "Labels Test",
            "gross_amount_cents": 4999,  # $49.99
            "net_amount_cents": 4750,
            "stripe_fee_cents": 249,
            "audit_type": "premium",
            "currency": "usd",
        }

        with patch("leadfactory.cost.purchase_metrics.record_metric") as mock_record_metric:
            self.tracker.record_purchase(**purchase_data)

            # Verify metrics were called with proper labels
            calls = mock_record_metric.call_args_list

            # Check that purchase metrics were recorded
            purchase_calls = [call for call in calls if len(call[0]) >= 1]
            assert len(purchase_calls) > 0

            # Verify at least one call included the expected audit_type label
            audit_type_calls = [
                call for call in calls
                if len(call) > 1 and call[1] and "audit_type" in call[1]
            ]
            assert any("premium" in str(call) for call in audit_type_calls)
