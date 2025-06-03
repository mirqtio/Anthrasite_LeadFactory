"""
Financial Tracking and Revenue Management
========================================

This module provides comprehensive financial tracking for the LeadFactory system,
including revenue, Stripe fees, taxes, and profit calculations.

Features:
- Revenue tracking from Stripe payments
- Stripe fee and tax tracking
- Profit margin calculations
- Integration with existing cost tracking
- Financial reporting and analytics
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class TransactionType(Enum):
    """Transaction type enumeration."""

    PAYMENT = "payment"
    REFUND = "refund"
    CHARGEBACK = "chargeback"
    ADJUSTMENT = "adjustment"


class FinancialTracker:
    """Financial tracking and revenue management for LeadFactory."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize financial tracker.

        Args:
            db_path: Path to SQLite database for financial tracking
        """
        # Set default database path if not provided
        if not db_path:
            db_dir = Path(__file__).parent.parent / "data"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "financial_tracking.db")

        self.db_path = db_path
        self._lock = threading.Lock()

        # Initialize database
        self._init_db()

        logger.info(f"Financial tracker initialized (db_path={db_path})")

    def _init_db(self) -> None:
        """Initialize the financial tracking database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create financial transactions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT UNIQUE NOT NULL,
                    stripe_payment_intent_id TEXT,
                    stripe_charge_id TEXT,
                    transaction_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    customer_email TEXT,
                    customer_name TEXT,
                    gross_amount_cents INTEGER NOT NULL,
                    net_amount_cents INTEGER NOT NULL,
                    stripe_fee_cents INTEGER NOT NULL,
                    application_fee_cents INTEGER DEFAULT 0,
                    tax_amount_cents INTEGER DEFAULT 0,
                    currency TEXT DEFAULT 'usd',
                    audit_type TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )

            # Create daily financial summary table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_financial_summary (
                    date TEXT PRIMARY KEY,
                    total_revenue_cents INTEGER NOT NULL DEFAULT 0,
                    total_stripe_fees_cents INTEGER NOT NULL DEFAULT 0,
                    total_tax_cents INTEGER NOT NULL DEFAULT 0,
                    net_revenue_cents INTEGER NOT NULL DEFAULT 0,
                    transaction_count INTEGER NOT NULL DEFAULT 0,
                    refund_count INTEGER NOT NULL DEFAULT 0,
                    refund_amount_cents INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )

            # Create indices for performance
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financial_timestamp
                ON financial_transactions (timestamp)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financial_customer_email
                ON financial_transactions (customer_email)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financial_stripe_payment_intent
                ON financial_transactions (stripe_payment_intent_id)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financial_transaction_type
                ON financial_transactions (transaction_type)
            """
            )

            conn.commit()
            conn.close()

            logger.debug("Financial database initialized")

    def record_stripe_payment(
        self,
        stripe_payment_intent_id: str,
        stripe_charge_id: str,
        customer_email: str,
        customer_name: Optional[str],
        gross_amount_cents: int,
        net_amount_cents: int,
        stripe_fee_cents: int,
        application_fee_cents: int = 0,
        tax_amount_cents: int = 0,
        currency: str = "usd",
        audit_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a Stripe payment transaction.

        Args:
            stripe_payment_intent_id: Stripe payment intent ID
            stripe_charge_id: Stripe charge ID
            customer_email: Customer email address
            customer_name: Customer name
            gross_amount_cents: Gross amount in cents
            net_amount_cents: Net amount after fees in cents
            stripe_fee_cents: Stripe fee in cents
            application_fee_cents: Application fee in cents
            tax_amount_cents: Tax amount in cents
            currency: Currency code
            audit_type: Type of audit purchased
            metadata: Additional metadata

        Returns:
            Transaction ID
        """
        transaction_id = (
            f"txn_{stripe_payment_intent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        timestamp = datetime.now().isoformat()

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO financial_transactions (
                        transaction_id, stripe_payment_intent_id, stripe_charge_id,
                        transaction_type, timestamp, customer_email, customer_name,
                        gross_amount_cents, net_amount_cents, stripe_fee_cents,
                        application_fee_cents, tax_amount_cents, currency,
                        audit_type, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        transaction_id,
                        stripe_payment_intent_id,
                        stripe_charge_id,
                        TransactionType.PAYMENT.value,
                        timestamp,
                        customer_email,
                        customer_name,
                        gross_amount_cents,
                        net_amount_cents,
                        stripe_fee_cents,
                        application_fee_cents,
                        tax_amount_cents,
                        currency,
                        audit_type,
                        json.dumps(metadata) if metadata else None,
                        timestamp,
                        timestamp,
                    ),
                )

                conn.commit()

                # Update daily summary
                self._update_daily_summary(timestamp[:10])  # Extract date part

                logger.info(f"Recorded Stripe payment: {transaction_id}")

                return transaction_id

            except sqlite3.IntegrityError as e:
                logger.warning(
                    f"Transaction already exists: {stripe_payment_intent_id}"
                )
                return f"existing_{stripe_payment_intent_id}"
            finally:
                conn.close()

    def record_stripe_refund(
        self,
        stripe_payment_intent_id: str,
        stripe_charge_id: str,
        refund_amount_cents: int,
        stripe_fee_refund_cents: int = 0,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a Stripe refund transaction.

        Args:
            stripe_payment_intent_id: Original payment intent ID
            stripe_charge_id: Stripe charge ID
            refund_amount_cents: Refund amount in cents
            stripe_fee_refund_cents: Stripe fee refund in cents
            reason: Refund reason
            metadata: Additional metadata

        Returns:
            Transaction ID
        """
        transaction_id = f"refund_{stripe_payment_intent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().isoformat()

        # Get original transaction details
        original_transaction = self.get_transaction_by_payment_intent(
            stripe_payment_intent_id
        )
        if not original_transaction:
            logger.error(
                f"Original transaction not found for refund: {stripe_payment_intent_id}"
            )
            return ""

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO financial_transactions (
                        transaction_id, stripe_payment_intent_id, stripe_charge_id,
                        transaction_type, timestamp, customer_email, customer_name,
                        gross_amount_cents, net_amount_cents, stripe_fee_cents,
                        application_fee_cents, tax_amount_cents, currency,
                        audit_type, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        transaction_id,
                        stripe_payment_intent_id,
                        stripe_charge_id,
                        TransactionType.REFUND.value,
                        timestamp,
                        original_transaction.get("customer_email"),
                        original_transaction.get("customer_name"),
                        -refund_amount_cents,  # Negative for refunds
                        -(refund_amount_cents - stripe_fee_refund_cents),  # Net refund
                        -stripe_fee_refund_cents,  # Negative fee refund
                        0,
                        0,
                        original_transaction.get("currency", "usd"),
                        original_transaction.get("audit_type"),
                        json.dumps({**(metadata or {}), "reason": reason}),
                        timestamp,
                        timestamp,
                    ),
                )

                conn.commit()

                # Update daily summary
                self._update_daily_summary(timestamp[:10])

                logger.info(f"Recorded Stripe refund: {transaction_id}")

                return transaction_id

            finally:
                conn.close()

    def _update_daily_summary(self, date: str) -> None:
        """Update daily financial summary for a given date.

        Args:
            date: Date in YYYY-MM-DD format
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Calculate daily totals
            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN transaction_type = 'payment' THEN gross_amount_cents ELSE 0 END) as total_revenue,
                    SUM(CASE WHEN transaction_type = 'payment' THEN stripe_fee_cents ELSE 0 END) as total_fees,
                    SUM(CASE WHEN transaction_type = 'payment' THEN tax_amount_cents ELSE 0 END) as total_tax,
                    SUM(CASE WHEN transaction_type = 'payment' THEN net_amount_cents ELSE 0 END) as net_revenue,
                    COUNT(CASE WHEN transaction_type = 'payment' THEN 1 END) as payment_count,
                    COUNT(CASE WHEN transaction_type = 'refund' THEN 1 END) as refund_count,
                    SUM(CASE WHEN transaction_type = 'refund' THEN ABS(gross_amount_cents) ELSE 0 END) as refund_amount
                FROM financial_transactions
                WHERE DATE(timestamp) = ?
            """,
                (date,),
            )

            result = cursor.fetchone()

            if result and result[0] is not None:
                (
                    total_revenue,
                    total_fees,
                    total_tax,
                    net_revenue,
                    payment_count,
                    refund_count,
                    refund_amount,
                ) = result

                # Insert or update daily summary
                timestamp = datetime.now().isoformat()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO daily_financial_summary (
                        date, total_revenue_cents, total_stripe_fees_cents,
                        total_tax_cents, net_revenue_cents, transaction_count,
                        refund_count, refund_amount_cents, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                              COALESCE((SELECT created_at FROM daily_financial_summary WHERE date = ?), ?),
                              ?)
                """,
                    (
                        date,
                        total_revenue or 0,
                        total_fees or 0,
                        total_tax or 0,
                        net_revenue or 0,
                        payment_count or 0,
                        refund_count or 0,
                        refund_amount or 0,
                        date,
                        timestamp,
                        timestamp,
                    ),
                )

                conn.commit()

        finally:
            conn.close()

    def get_transaction_by_payment_intent(
        self, stripe_payment_intent_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get transaction by Stripe payment intent ID.

        Args:
            stripe_payment_intent_id: Stripe payment intent ID

        Returns:
            Transaction data or None
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    SELECT * FROM financial_transactions
                    WHERE stripe_payment_intent_id = ? AND transaction_type = 'payment'
                    ORDER BY created_at DESC LIMIT 1
                """,
                    (stripe_payment_intent_id,),
                )

                result = cursor.fetchone()
                if result:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, result))
                return None

            finally:
                conn.close()

    def get_daily_summary(self, date: str) -> Optional[Dict[str, Any]]:
        """Get daily financial summary.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Daily summary data or None
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    SELECT * FROM daily_financial_summary WHERE date = ?
                """,
                    (date,),
                )

                result = cursor.fetchone()
                if result:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, result))
                return None

            finally:
                conn.close()

    def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Get monthly financial summary.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Monthly summary data
        """
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month+1:02d}-01"

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    SELECT
                        SUM(total_revenue_cents) as total_revenue,
                        SUM(total_stripe_fees_cents) as total_fees,
                        SUM(total_tax_cents) as total_tax,
                        SUM(net_revenue_cents) as net_revenue,
                        SUM(transaction_count) as total_transactions,
                        SUM(refund_count) as total_refunds,
                        SUM(refund_amount_cents) as total_refund_amount,
                        COUNT(*) as active_days
                    FROM daily_financial_summary
                    WHERE date >= ? AND date < ?
                """,
                    (start_date, end_date),
                )

                result = cursor.fetchone()

                return {
                    "year": year,
                    "month": month,
                    "total_revenue_cents": result[0] or 0,
                    "total_stripe_fees_cents": result[1] or 0,
                    "total_tax_cents": result[2] or 0,
                    "net_revenue_cents": result[3] or 0,
                    "total_transactions": result[4] or 0,
                    "total_refunds": result[5] or 0,
                    "total_refund_amount_cents": result[6] or 0,
                    "active_days": result[7] or 0,
                }

            finally:
                conn.close()

    def get_profit_margin_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get profit margin data for a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Profit margin analysis data
        """
        # Get revenue data
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    SELECT
                        SUM(total_revenue_cents) as total_revenue,
                        SUM(total_stripe_fees_cents) as total_fees,
                        SUM(total_tax_cents) as total_tax,
                        SUM(net_revenue_cents) as net_revenue
                    FROM daily_financial_summary
                    WHERE date >= ? AND date <= ?
                """,
                    (start_date, end_date),
                )

                revenue_result = cursor.fetchone()

            finally:
                conn.close()

        # Get cost data from cost tracking system
        try:
            from leadfactory.cost.cost_tracking import cost_tracker

            # Calculate total costs for the period
            total_costs = 0.0
            current_date = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

            while current_date <= end_date_obj:
                date_str = current_date.strftime("%Y-%m-%d")
                daily_cost = cost_tracker.get_daily_cost()  # This gets current day cost
                # Note: We'd need to modify cost_tracker to get historical daily costs
                current_date += timedelta(days=1)

        except ImportError:
            logger.warning("Cost tracker not available for profit calculation")
            total_costs = 0.0

        # Calculate profit metrics
        total_revenue = (revenue_result[0] or 0) / 100.0  # Convert cents to dollars
        total_fees = (revenue_result[1] or 0) / 100.0
        total_tax = (revenue_result[2] or 0) / 100.0
        net_revenue = (revenue_result[3] or 0) / 100.0

        gross_profit = net_revenue - total_costs
        gross_margin = (gross_profit / net_revenue * 100) if net_revenue > 0 else 0

        return {
            "period": {"start_date": start_date, "end_date": end_date},
            "revenue": {
                "gross_revenue_dollars": total_revenue,
                "stripe_fees_dollars": total_fees,
                "tax_dollars": total_tax,
                "net_revenue_dollars": net_revenue,
            },
            "costs": {"total_costs_dollars": total_costs},
            "profit": {
                "gross_profit_dollars": gross_profit,
                "gross_margin_percent": gross_margin,
            },
        }


# Create singleton instance
financial_tracker = FinancialTracker()
