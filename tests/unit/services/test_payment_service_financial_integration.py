"""
Unit tests for Payment Service Financial Integration
==================================================

Tests the integration between the payment service and financial tracking system,
ensuring Stripe fees and taxes are properly captured and recorded.
"""

import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from leadfactory.services.payment_service import StripePaymentService, PaymentStatus
from leadfactory.cost.financial_tracking import FinancialTracker


class TestPaymentServiceFinancialIntegration(unittest.TestCase):
    """Test payment service integration with financial tracking."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Stripe configuration
        self.mock_config = Mock()
        self.mock_config.stripe_secret_key = "sk_test_123"
        self.mock_config.webhook_secret = "whsec_test_123"

        # Mock database session
        self.mock_session = Mock()
        self.mock_session_context = Mock()
        self.mock_session_context.__enter__ = Mock(return_value=self.mock_session)
        self.mock_session_context.__exit__ = Mock(return_value=None)
        self.mock_session_local = Mock(return_value=self.mock_session_context)

        # Create payment service instance
        with patch('leadfactory.services.payment_service.stripe'):
            with patch('leadfactory.services.payment_service.create_engine'):
                with patch('leadfactory.services.payment_service.sessionmaker', return_value=self.mock_session_local):
                    self.payment_service = StripePaymentService(self.mock_config, "sqlite:///:memory:")

    @patch('leadfactory.services.payment_service.financial_tracker')
    @patch('leadfactory.services.payment_service.stripe')
    def test_payment_succeeded_records_financial_data(self, mock_stripe, mock_financial_tracker):
        """Test that successful payments record financial data."""
        # Mock payment record
        mock_payment = Mock()
        mock_payment.id = 1
        mock_payment.customer_email = "test@example.com"
        mock_payment.customer_name = "Test Customer"
        mock_payment.audit_type = "lead_audit"

        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_payment

        # Mock Stripe charge data
        mock_charge = {
            'id': 'ch_test_123',
            'amount': 5000,  # $50.00
            'amount_captured': 5000,
            'currency': 'usd',
            'balance_transaction': 'txn_test_123',
            'metadata': {'tax_amount': '500'},  # $5.00 tax
            'payment_method_details': {'type': 'card'},
            'receipt_url': 'https://pay.stripe.com/receipts/test'
        }

        mock_balance_txn = {
            'fee': 175,  # $1.75 Stripe fee
            'net': 4825,  # $48.25 net
            'fee_details': [
                {'type': 'stripe_fee', 'amount': 175}
            ]
        }

        # Mock Stripe API calls
        mock_stripe.Charge.list.return_value.data = [mock_charge]
        mock_stripe.BalanceTransaction.retrieve.return_value = mock_balance_txn

        # Mock payment intent data
        payment_intent = {
            'id': 'pi_test_123'
        }

        # Call the method
        result = self.payment_service._handle_payment_succeeded(payment_intent)

        # Verify payment status was updated
        self.assertEqual(mock_payment.status, PaymentStatus.SUCCEEDED.value)
        self.assertTrue(mock_payment.webhook_received)

        # Verify financial tracking was called
        mock_financial_tracker.record_stripe_payment.assert_called_once()
        call_args = mock_financial_tracker.record_stripe_payment.call_args[1]

        self.assertEqual(call_args['stripe_payment_intent_id'], 'pi_test_123')
        self.assertEqual(call_args['stripe_charge_id'], 'ch_test_123')
        self.assertEqual(call_args['customer_email'], 'test@example.com')
        self.assertEqual(call_args['gross_amount_cents'], 5000)
        self.assertEqual(call_args['net_amount_cents'], 4825)
        self.assertEqual(call_args['stripe_fee_cents'], 175)
        self.assertEqual(call_args['tax_amount_cents'], 500)
        self.assertEqual(call_args['currency'], 'usd')

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['payment_id'], 1)

    @patch('leadfactory.services.payment_service.financial_tracker')
    @patch('leadfactory.services.payment_service.stripe')
    def test_payment_succeeded_handles_missing_balance_transaction(self, mock_stripe, mock_financial_tracker):
        """Test payment succeeded handling when balance transaction is missing."""
        # Mock payment record
        mock_payment = Mock()
        mock_payment.id = 1
        mock_payment.customer_email = "test@example.com"
        mock_payment.customer_name = "Test Customer"
        mock_payment.audit_type = "lead_audit"

        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_payment

        # Mock Stripe charge data without balance transaction
        mock_charge = {
            'id': 'ch_test_123',
            'amount': 5000,
            'amount_captured': 5000,
            'currency': 'usd',
            'balance_transaction': None,
            'metadata': {},
            'payment_method_details': {'type': 'card'}
        }

        mock_stripe.Charge.list.return_value.data = [mock_charge]

        payment_intent = {'id': 'pi_test_123'}

        # Call the method
        result = self.payment_service._handle_payment_succeeded(payment_intent)

        # Verify financial tracking was still called with defaults
        mock_financial_tracker.record_stripe_payment.assert_called_once()
        call_args = mock_financial_tracker.record_stripe_payment.call_args[1]

        self.assertEqual(call_args['stripe_fee_cents'], 0)
        self.assertEqual(call_args['application_fee_cents'], 0)
        self.assertEqual(call_args['tax_amount_cents'], 0)

        self.assertEqual(result['status'], 'success')

    @patch('leadfactory.services.payment_service.financial_tracker')
    @patch('leadfactory.services.payment_service.stripe')
    def test_payment_succeeded_handles_stripe_api_error(self, mock_stripe, mock_financial_tracker):
        """Test payment succeeded handling when Stripe API fails."""
        # Mock payment record
        mock_payment = Mock()
        mock_payment.id = 1
        mock_payment.customer_email = "test@example.com"
        mock_payment.customer_name = "Test Customer"
        mock_payment.audit_type = "lead_audit"

        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_payment

        # Mock Stripe API to raise exception
        mock_stripe.Charge.list.side_effect = Exception("Stripe API error")

        payment_intent = {'id': 'pi_test_123'}

        # Call the method
        result = self.payment_service._handle_payment_succeeded(payment_intent)

        # Verify payment status was still updated
        self.assertEqual(mock_payment.status, PaymentStatus.SUCCEEDED.value)

        # Verify financial tracking was not called due to error
        mock_financial_tracker.record_stripe_payment.assert_not_called()

        # Verify result is still success (payment processing continues)
        self.assertEqual(result['status'], 'success')

    @patch('leadfactory.services.payment_service.financial_tracker')
    @patch('leadfactory.services.payment_service.stripe')
    def test_refund_created_records_financial_data(self, mock_stripe, mock_financial_tracker):
        """Test that refunds record financial data."""
        # Mock payment record
        mock_payment = Mock()
        mock_payment.id = 1
        mock_payment.customer_email = "test@example.com"
        mock_payment.customer_name = "Test Customer"

        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_payment

        # Mock balance transaction for refund
        mock_balance_txn = {
            'fee': -50,  # Negative fee (refunded)
        }

        mock_stripe.BalanceTransaction.retrieve.return_value = mock_balance_txn

        # Mock refund data
        refund = {
            'id': 'ref_test_123',
            'charge': 'ch_test_123',
            'payment_intent': 'pi_test_123',
            'amount': 2500,  # $25.00 refund
            'reason': 'requested_by_customer',
            'balance_transaction': 'txn_refund_123',
            'status': 'succeeded',
            'metadata': {'reason': 'customer_request'}
        }

        # Call the method
        result = self.payment_service._handle_refund_created(refund)

        # Verify payment status was updated
        self.assertEqual(mock_payment.status, PaymentStatus.REFUNDED.value)

        # Verify financial tracking was called
        mock_financial_tracker.record_stripe_refund.assert_called_once()
        call_args = mock_financial_tracker.record_stripe_refund.call_args[1]

        self.assertEqual(call_args['stripe_payment_intent_id'], 'pi_test_123')
        self.assertEqual(call_args['stripe_charge_id'], 'ch_test_123')
        self.assertEqual(call_args['refund_amount_cents'], 2500)
        self.assertEqual(call_args['stripe_fee_refund_cents'], 50)  # Absolute value
        self.assertEqual(call_args['reason'], 'requested_by_customer')

        # Verify result
        self.assertEqual(result['status'], 'refunded')
        self.assertEqual(result['payment_id'], 1)

    @patch('leadfactory.services.payment_service.financial_tracker')
    def test_refund_created_handles_missing_payment(self, mock_financial_tracker):
        """Test refund handling when payment record is not found."""
        # Mock no payment found
        self.mock_session.query.return_value.filter.return_value.first.return_value = None

        refund = {
            'id': 'ref_test_123',
            'charge': 'ch_test_123',
            'payment_intent': 'pi_test_123',
            'amount': 2500,
            'reason': 'requested_by_customer'
        }

        # Call the method
        result = self.payment_service._handle_refund_created(refund)

        # Verify financial tracking was not called
        mock_financial_tracker.record_stripe_refund.assert_not_called()

        # Verify result
        self.assertEqual(result['status'], 'not_found')
        self.assertEqual(result['payment_intent_id'], 'pi_test_123')

    @patch('leadfactory.services.payment_service.financial_tracker')
    @patch('leadfactory.services.payment_service.stripe')
    def test_refund_created_handles_balance_transaction_error(self, mock_stripe, mock_financial_tracker):
        """Test refund handling when balance transaction retrieval fails."""
        # Mock payment record
        mock_payment = Mock()
        mock_payment.id = 1
        mock_payment.customer_email = "test@example.com"

        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_payment

        # Mock Stripe API to raise exception
        mock_stripe.BalanceTransaction.retrieve.side_effect = Exception("API error")

        refund = {
            'id': 'ref_test_123',
            'charge': 'ch_test_123',
            'payment_intent': 'pi_test_123',
            'amount': 2500,
            'reason': 'requested_by_customer',
            'balance_transaction': 'txn_refund_123'
        }

        # Call the method
        result = self.payment_service._handle_refund_created(refund)

        # Verify payment status was updated
        self.assertEqual(mock_payment.status, PaymentStatus.REFUNDED.value)

        # Verify financial tracking was called with default fee refund
        mock_financial_tracker.record_stripe_refund.assert_called_once()
        call_args = mock_financial_tracker.record_stripe_refund.call_args[1]
        self.assertEqual(call_args['stripe_fee_refund_cents'], 0)

        self.assertEqual(result['status'], 'refunded')

    @patch('leadfactory.services.payment_service.stripe.Webhook.construct_event')
    def test_webhook_handler_routes_refund_events(self, mock_construct_event):
        """Test that webhook handler properly routes refund events."""
        # Mock refund event
        mock_event = {
            'type': 'refund.created',
            'data': {
                'object': {
                    'id': 'ref_test_123',
                    'charge': 'ch_test_123',
                    'payment_intent': 'pi_test_123',
                    'amount': 2500
                }
            }
        }

        mock_construct_event.return_value = mock_event

        # Mock the refund handler
        with patch.object(self.payment_service, '_handle_refund_created') as mock_refund_handler:
            mock_refund_handler.return_value = {'status': 'refunded'}

            result = self.payment_service.handle_webhook('payload', 'signature')

            # Verify refund handler was called
            mock_refund_handler.assert_called_once_with(mock_event['data']['object'])
            self.assertEqual(result['status'], 'refunded')

    def test_chargeback_created_updates_payment_status(self):
        """Test that chargebacks update payment status to failed."""
        # Mock payment record
        mock_payment = Mock()
        mock_payment.id = 1
        mock_payment.customer_email = "test@example.com"

        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_payment

        dispute = {
            'charge': 'ch_test_123',
            'payment_intent': 'pi_test_123'
        }

        # Call the method
        result = self.payment_service._handle_chargeback_created(dispute)

        # Verify payment status was updated to failed
        self.assertEqual(mock_payment.status, PaymentStatus.FAILED.value)

        # Verify result
        self.assertEqual(result['status'], 'chargeback')
        self.assertEqual(result['payment_id'], 1)


if __name__ == '__main__':
    unittest.main()
