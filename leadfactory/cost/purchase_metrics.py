"""
Purchase Metrics and Analytics
=============================

This module provides comprehensive purchase metrics collection and analysis
for the LeadFactory audit business model. It integrates with the financial
tracking system and Prometheus metrics to provide real-time revenue insights.

Features:
- Real-time purchase tracking
- Revenue analytics and conversion metrics
- Customer lifetime value calculations
- Audit type performance analysis
- Integration with Prometheus monitoring
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.cost.financial_tracking import FinancialTracker, financial_tracker
from leadfactory.utils.logging import get_logger
from leadfactory.utils.metrics import (
    AVERAGE_ORDER_VALUE,
    CONVERSION_FUNNEL,
    CUSTOMER_LIFETIME_VALUE,
    DAILY_REVENUE,
    MONTHLY_RECURRING_REVENUE,
    PURCHASES_TOTAL,
    REFUND_AMOUNT_TOTAL,
    REFUNDS_TOTAL,
    REVENUE_TOTAL,
    STRIPE_FEES_TOTAL,
    record_metric,
)

logger = get_logger(__name__)


class PurchaseMetricsTracker:
    """Purchase metrics tracking and analytics for LeadFactory audit business."""

    def __init__(self, financial_tracker: Optional[FinancialTracker] = None):
        """Initialize purchase metrics tracker.

        Args:
            financial_tracker: Optional financial tracker instance (uses singleton if not provided)
        """
        self.financial_tracker = financial_tracker or financial_tracker
        logger.info("Purchase metrics tracker initialized")

    def record_purchase(
        self,
        stripe_payment_intent_id: str,
        stripe_charge_id: str,
        customer_email: str,
        customer_name: Optional[str],
        gross_amount_cents: int,
        net_amount_cents: int,
        stripe_fee_cents: int,
        audit_type: str,
        currency: str = "usd",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Record a successful purchase and update metrics.

        Args:
            stripe_payment_intent_id: Stripe payment intent ID
            stripe_charge_id: Stripe charge ID
            customer_email: Customer email address
            customer_name: Customer name
            gross_amount_cents: Gross amount in cents
            net_amount_cents: Net amount after fees in cents
            stripe_fee_cents: Stripe fee in cents
            audit_type: Type of audit purchased (e.g., 'basic', 'premium', 'enterprise')
            currency: Currency code
            metadata: Additional metadata

        Returns:
            Transaction ID
        """
        # Record in financial tracking system
        transaction_id = self.financial_tracker.record_stripe_payment(
            stripe_payment_intent_id=stripe_payment_intent_id,
            stripe_charge_id=stripe_charge_id,
            customer_email=customer_email,
            customer_name=customer_name,
            gross_amount_cents=gross_amount_cents,
            net_amount_cents=net_amount_cents,
            stripe_fee_cents=stripe_fee_cents,
            audit_type=audit_type,
            currency=currency,
            metadata=metadata,
        )

        # Update Prometheus metrics
        self._update_purchase_metrics(
            audit_type=audit_type,
            currency=currency,
            gross_amount_cents=gross_amount_cents,
            stripe_fee_cents=stripe_fee_cents,
            customer_email=customer_email,
        )

        # Update aggregated metrics
        self._update_aggregated_metrics()

        logger.info(
            f"Purchase recorded: {transaction_id}",
            extra={
                "transaction_id": transaction_id,
                "audit_type": audit_type,
                "amount_cents": gross_amount_cents,
                "customer_email": customer_email,
            },
        )

        return transaction_id

    def record_refund(
        self,
        stripe_payment_intent_id: str,
        stripe_charge_id: str,
        refund_amount_cents: int,
        reason: str,
        currency: str = "usd",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Record a refund and update metrics.

        Args:
            stripe_payment_intent_id: Original payment intent ID
            stripe_charge_id: Stripe charge ID
            refund_amount_cents: Refund amount in cents
            reason: Refund reason
            currency: Currency code
            metadata: Additional metadata

        Returns:
            Transaction ID
        """
        # Record in financial tracking system
        transaction_id = self.financial_tracker.record_stripe_refund(
            stripe_payment_intent_id=stripe_payment_intent_id,
            stripe_charge_id=stripe_charge_id,
            refund_amount_cents=refund_amount_cents,
            reason=reason,
            metadata=metadata,
        )

        # Update Prometheus metrics
        record_metric(REFUNDS_TOTAL, 1, reason=reason, currency=currency)
        record_metric(REFUND_AMOUNT_TOTAL, refund_amount_cents, currency=currency)

        # Update aggregated metrics
        self._update_aggregated_metrics()

        logger.info(
            f"Refund recorded: {transaction_id}",
            extra={
                "transaction_id": transaction_id,
                "refund_amount_cents": refund_amount_cents,
                "reason": reason,
            },
        )

        return transaction_id

    def _update_purchase_metrics(
        self,
        audit_type: str,
        currency: str,
        gross_amount_cents: int,
        stripe_fee_cents: int,
        customer_email: str,
    ) -> None:
        """Update Prometheus metrics for a purchase."""
        # Record purchase count and revenue
        record_metric(PURCHASES_TOTAL, 1, audit_type=audit_type, currency=currency)
        record_metric(
            REVENUE_TOTAL, gross_amount_cents, audit_type=audit_type, currency=currency
        )
        record_metric(STRIPE_FEES_TOTAL, stripe_fee_cents, currency=currency)

        logger.debug(
            "Purchase metrics updated",
            extra={
                "audit_type": audit_type,
                "currency": currency,
                "gross_amount_cents": gross_amount_cents,
                "stripe_fee_cents": stripe_fee_cents,
            },
        )

    def _update_aggregated_metrics(self) -> None:
        """Update aggregated metrics like averages and totals."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            # Update daily revenue
            daily_summary = self.financial_tracker.get_daily_summary(today)
            if daily_summary:
                record_metric(
                    DAILY_REVENUE,
                    daily_summary["total_revenue_cents"],
                    date=today,
                )

            # Update average order values by audit type
            self._update_average_order_values()

            # Update monthly recurring revenue
            self._update_monthly_metrics()

        except Exception as e:
            logger.error(
                f"Failed to update aggregated metrics: {e}",
                extra={"error": str(e)},
            )

    def _update_average_order_values(self) -> None:
        """Update average order value metrics by audit type."""
        # Get recent transactions to calculate AOV
        # This would need additional queries to the financial tracker
        # For now, we'll calculate based on available daily summaries

        try:
            # Get last 30 days of data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            # This is a simplified version - in production we'd want more detailed AOV calculation
            profit_data = self.financial_tracker.get_profit_margin_data(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            if profit_data["revenue"]["net_revenue_dollars"] > 0:
                # Estimate AOV (this could be made more precise with audit type breakdown)
                estimated_aov_cents = int(
                    profit_data["revenue"]["gross_revenue_dollars"] * 100
                )
                record_metric(
                    AVERAGE_ORDER_VALUE, estimated_aov_cents, audit_type="all"
                )

        except Exception as e:
            logger.debug(f"Could not update AOV metrics: {e}")

    def _update_monthly_metrics(self) -> None:
        """Update monthly recurring revenue and related metrics."""
        try:
            now = datetime.now()
            monthly_summary = self.financial_tracker.get_monthly_summary(
                now.year, now.month
            )

            if monthly_summary["total_revenue_cents"] > 0:
                record_metric(
                    MONTHLY_RECURRING_REVENUE, monthly_summary["total_revenue_cents"]
                )

        except Exception as e:
            logger.debug(f"Could not update monthly metrics: {e}")

    def get_conversion_metrics(self, audit_type: str = "all") -> dict[str, Any]:
        """Get conversion funnel metrics for audit sales.

        Args:
            audit_type: Specific audit type or 'all' for aggregate

        Returns:
            Conversion metrics data
        """
        try:
            # Get last 30 days of data for conversion analysis
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            monthly_summary = self.financial_tracker.get_monthly_summary(
                end_date.year, end_date.month
            )

            # Calculate basic conversion metrics
            total_purchases = monthly_summary["total_transactions"]
            total_revenue_cents = monthly_summary["total_revenue_cents"]

            conversion_data = {
                "period": {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                },
                "audit_type": audit_type,
                "metrics": {
                    "total_purchases": total_purchases,
                    "total_revenue_cents": total_revenue_cents,
                    "average_order_value_cents": (
                        total_revenue_cents // total_purchases
                        if total_purchases > 0
                        else 0
                    ),
                },
            }

            # Update Prometheus conversion funnel metrics
            if total_purchases > 0:
                aov_cents = total_revenue_cents // total_purchases
                record_metric(
                    CONVERSION_FUNNEL,
                    aov_cents,
                    stage="purchase",
                    audit_type=audit_type,
                )

            return conversion_data

        except Exception as e:
            logger.error(
                f"Failed to get conversion metrics: {e}",
                extra={"error": str(e), "audit_type": audit_type},
            )
            return {
                "period": {"start_date": "", "end_date": ""},
                "audit_type": audit_type,
                "metrics": {},
                "error": str(e),
            }

    def get_customer_lifetime_value(self, days_window: int = 365) -> float:
        """Calculate and update customer lifetime value metrics.

        Args:
            days_window: Number of days to look back for CLV calculation

        Returns:
            Customer lifetime value in dollars
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_window)

            profit_data = self.financial_tracker.get_profit_margin_data(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            # Simple CLV calculation (revenue per customer over time window)
            revenue_dollars = profit_data["revenue"]["net_revenue_dollars"]

            # Estimate unique customers (this could be improved with actual customer tracking)
            monthly_summary = self.financial_tracker.get_monthly_summary(
                end_date.year, end_date.month
            )
            estimated_customers = max(
                1, monthly_summary["total_transactions"] // 2
            )  # Rough estimate

            clv_dollars = (
                revenue_dollars / estimated_customers if estimated_customers > 0 else 0
            )
            clv_cents = int(clv_dollars * 100)

            # Update CLV metric
            record_metric(CUSTOMER_LIFETIME_VALUE, clv_cents)

            logger.info(
                f"Customer lifetime value calculated: ${clv_dollars:.2f}",
                extra={
                    "clv_dollars": clv_dollars,
                    "revenue_dollars": revenue_dollars,
                    "estimated_customers": estimated_customers,
                    "days_window": days_window,
                },
            )

            return clv_dollars

        except Exception as e:
            logger.error(
                f"Failed to calculate customer lifetime value: {e}",
                extra={"error": str(e), "days_window": days_window},
            )
            return 0.0

    def get_purchase_analytics_summary(self) -> dict[str, Any]:
        """Get comprehensive purchase analytics summary.

        Returns:
            Analytics summary with key business metrics
        """
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")

            # Get daily and monthly summaries
            daily_summary = self.financial_tracker.get_daily_summary(today)
            monthly_summary = self.financial_tracker.get_monthly_summary(
                now.year, now.month
            )

            # Get profit data for last 30 days
            start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            profit_data = self.financial_tracker.get_profit_margin_data(
                start_date, today
            )

            # Calculate CLV
            clv_dollars = self.get_customer_lifetime_value()

            summary = {
                "timestamp": now.isoformat(),
                "daily_metrics": daily_summary or {},
                "monthly_metrics": monthly_summary,
                "profit_analysis": profit_data,
                "customer_metrics": {
                    "lifetime_value_dollars": clv_dollars,
                },
                "conversion_metrics": self.get_conversion_metrics(),
            }

            logger.info("Purchase analytics summary generated")
            return summary

        except Exception as e:
            logger.error(
                f"Failed to generate purchase analytics summary: {e}",
                extra={"error": str(e)},
            )
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }


# Create singleton instance
purchase_metrics_tracker = PurchaseMetricsTracker()
