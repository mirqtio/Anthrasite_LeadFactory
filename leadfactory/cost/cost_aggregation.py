"""
Cost Aggregation Service
=======================

This module provides comprehensive cost and revenue aggregation for the LeadFactory system,
combining operational costs with financial data from Stripe payments.

Features:
- Daily cost and revenue aggregation
- Profit margin calculations
- Integration with cost tracking and financial tracking
- Business intelligence reporting
- Grafana dashboard data preparation
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class CostAggregationService:
    """Service for aggregating costs and revenue data."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize cost aggregation service.

        Args:
            db_path: Path to SQLite database for aggregated data
        """
        # Set default database path if not provided
        if not db_path:
            db_dir = Path(__file__).parent.parent / "data"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "cost_aggregation.db")

        self.db_path = db_path
        self._lock = threading.Lock()

        # Initialize database
        self._init_db()

        # Import tracking services
        self._init_tracking_services()

        logger.info(f"Cost aggregation service initialized (db_path={db_path})")

    def _init_db(self) -> None:
        """Initialize the cost aggregation database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create daily aggregation table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_cost_revenue_summary (
                    date TEXT PRIMARY KEY,

                    -- Revenue data (in cents)
                    gross_revenue_cents INTEGER NOT NULL DEFAULT 0,
                    net_revenue_cents INTEGER NOT NULL DEFAULT 0,
                    stripe_fees_cents INTEGER NOT NULL DEFAULT 0,
                    tax_amount_cents INTEGER NOT NULL DEFAULT 0,
                    transaction_count INTEGER NOT NULL DEFAULT 0,
                    refund_count INTEGER NOT NULL DEFAULT 0,
                    refund_amount_cents INTEGER NOT NULL DEFAULT 0,

                    -- Cost data (in dollars, converted to cents for consistency)
                    total_operational_costs_cents INTEGER NOT NULL DEFAULT 0,
                    openai_costs_cents INTEGER NOT NULL DEFAULT 0,
                    semrush_costs_cents INTEGER NOT NULL DEFAULT 0,
                    gpu_costs_cents INTEGER NOT NULL DEFAULT 0,
                    other_api_costs_cents INTEGER NOT NULL DEFAULT 0,

                    -- Profit calculations (in cents)
                    gross_profit_cents INTEGER NOT NULL DEFAULT 0,
                    net_profit_cents INTEGER NOT NULL DEFAULT 0,
                    gross_margin_percent REAL NOT NULL DEFAULT 0.0,
                    net_margin_percent REAL NOT NULL DEFAULT 0.0,

                    -- Metadata
                    last_updated TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """
            )

            # Create monthly aggregation table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_cost_revenue_summary (
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,

                    -- Revenue data (in cents)
                    gross_revenue_cents INTEGER NOT NULL DEFAULT 0,
                    net_revenue_cents INTEGER NOT NULL DEFAULT 0,
                    stripe_fees_cents INTEGER NOT NULL DEFAULT 0,
                    tax_amount_cents INTEGER NOT NULL DEFAULT 0,
                    transaction_count INTEGER NOT NULL DEFAULT 0,
                    refund_count INTEGER NOT NULL DEFAULT 0,
                    refund_amount_cents INTEGER NOT NULL DEFAULT 0,

                    -- Cost data (in cents)
                    total_operational_costs_cents INTEGER NOT NULL DEFAULT 0,
                    openai_costs_cents INTEGER NOT NULL DEFAULT 0,
                    semrush_costs_cents INTEGER NOT NULL DEFAULT 0,
                    gpu_costs_cents INTEGER NOT NULL DEFAULT 0,
                    other_api_costs_cents INTEGER NOT NULL DEFAULT 0,

                    -- Profit calculations (in cents)
                    gross_profit_cents INTEGER NOT NULL DEFAULT 0,
                    net_profit_cents INTEGER NOT NULL DEFAULT 0,
                    gross_margin_percent REAL NOT NULL DEFAULT 0.0,
                    net_margin_percent REAL NOT NULL DEFAULT 0.0,

                    -- Metadata
                    active_days INTEGER NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL,
                    created_at TEXT NOT NULL,

                    PRIMARY KEY (year, month)
                )
            """
            )

            # Create indices
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_daily_summary_date
                ON daily_cost_revenue_summary (date)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_monthly_summary_year_month
                ON monthly_cost_revenue_summary (year, month)
            """
            )

            conn.commit()
            conn.close()

            logger.debug("Cost aggregation database initialized")

    def _init_tracking_services(self) -> None:
        """Initialize connections to tracking services."""
        try:
            from leadfactory.cost.cost_tracking import cost_tracker

            self.cost_tracker = cost_tracker
        except ImportError:
            logger.warning("Cost tracker not available")
            self.cost_tracker = None

        try:
            from leadfactory.cost.financial_tracking import financial_tracker

            self.financial_tracker = financial_tracker
        except ImportError:
            logger.warning("Financial tracker not available")
            self.financial_tracker = None

    def aggregate_daily_data(self, date: str) -> Dict[str, Any]:
        """Aggregate cost and revenue data for a specific date.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Aggregated data dictionary
        """
        logger.info(f"Aggregating daily data for {date}")

        # Get financial data
        financial_data = self._get_daily_financial_data(date)

        # Get cost data
        cost_data = self._get_daily_cost_data(date)

        # Calculate profit metrics
        gross_revenue_cents = financial_data.get("gross_revenue_cents", 0)
        net_revenue_cents = financial_data.get("net_revenue_cents", 0)
        total_costs_cents = cost_data.get("total_costs_cents", 0)

        gross_profit_cents = gross_revenue_cents - total_costs_cents
        net_profit_cents = net_revenue_cents - total_costs_cents

        gross_margin_percent = (
            (gross_profit_cents / gross_revenue_cents * 100)
            if gross_revenue_cents > 0
            else 0
        )
        net_margin_percent = (
            (net_profit_cents / net_revenue_cents * 100) if net_revenue_cents > 0 else 0
        )

        # Prepare aggregated data
        aggregated_data = {
            "date": date,
            # Revenue data
            "gross_revenue_cents": gross_revenue_cents,
            "net_revenue_cents": net_revenue_cents,
            "stripe_fees_cents": financial_data.get("stripe_fees_cents", 0),
            "tax_amount_cents": financial_data.get("tax_amount_cents", 0),
            "transaction_count": financial_data.get("transaction_count", 0),
            "refund_count": financial_data.get("refund_count", 0),
            "refund_amount_cents": financial_data.get("refund_amount_cents", 0),
            # Cost data
            "total_operational_costs_cents": total_costs_cents,
            "openai_costs_cents": cost_data.get("openai_costs_cents", 0),
            "semrush_costs_cents": cost_data.get("semrush_costs_cents", 0),
            "gpu_costs_cents": cost_data.get("gpu_costs_cents", 0),
            "other_api_costs_cents": cost_data.get("other_api_costs_cents", 0),
            # Profit calculations
            "gross_profit_cents": gross_profit_cents,
            "net_profit_cents": net_profit_cents,
            "gross_margin_percent": gross_margin_percent,
            "net_margin_percent": net_margin_percent,
            # Metadata
            "last_updated": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
        }

        # Store in database
        self._store_daily_aggregation(aggregated_data)

        logger.info(
            f"Daily aggregation completed for {date}: "
            f"revenue=${gross_revenue_cents/100:.2f}, "
            f"costs=${total_costs_cents/100:.2f}, "
            f"profit=${gross_profit_cents/100:.2f}"
        )

        return aggregated_data

    def _get_daily_financial_data(self, date: str) -> Dict[str, Any]:
        """Get daily financial data from financial tracker.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Financial data dictionary
        """
        if not self.financial_tracker:
            return {}

        try:
            daily_summary = self.financial_tracker.get_daily_summary(date)
            if daily_summary:
                return {
                    "gross_revenue_cents": daily_summary.get("total_revenue_cents", 0),
                    "net_revenue_cents": daily_summary.get("net_revenue_cents", 0),
                    "stripe_fees_cents": daily_summary.get(
                        "total_stripe_fees_cents", 0
                    ),
                    "tax_amount_cents": daily_summary.get("total_tax_cents", 0),
                    "transaction_count": daily_summary.get("transaction_count", 0),
                    "refund_count": daily_summary.get("refund_count", 0),
                    "refund_amount_cents": daily_summary.get("refund_amount_cents", 0),
                }
        except Exception as e:
            logger.error(f"Error getting financial data for {date}: {e}")

        return {}

    def _get_daily_cost_data(self, date: str) -> Dict[str, Any]:
        """Get daily cost data from cost tracker.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Cost data dictionary
        """
        if not self.cost_tracker:
            return {}

        try:
            # Note: The current cost_tracker doesn't have historical daily cost retrieval
            # We'll need to enhance it or query the database directly
            cost_data = self._query_cost_tracker_database(date)
            return cost_data
        except Exception as e:
            logger.error(f"Error getting cost data for {date}: {e}")

        return {}

    def _query_cost_tracker_database(self, date: str) -> Dict[str, Any]:
        """Query cost tracker database directly for historical data.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Cost data dictionary
        """
        if not self.cost_tracker:
            return {}

        try:
            # Get cost tracker database path
            cost_db_path = self.cost_tracker.db_path

            conn = sqlite3.connect(cost_db_path)
            cursor = conn.cursor()

            # Query costs for the specific date
            cursor.execute(
                """
                SELECT
                    service,
                    SUM(amount) as total_amount
                FROM costs
                WHERE DATE(timestamp) = ?
                GROUP BY service
            """,
                (date,),
            )

            results = cursor.fetchall()
            conn.close()

            # Organize costs by service
            cost_data = {
                "total_costs_cents": 0,
                "openai_costs_cents": 0,
                "semrush_costs_cents": 0,
                "gpu_costs_cents": 0,
                "other_api_costs_cents": 0,
            }

            for service, amount in results:
                amount_cents = int(amount * 100)  # Convert dollars to cents
                cost_data["total_costs_cents"] += amount_cents

                if service.lower() in ["openai", "gpt", "chatgpt"]:
                    cost_data["openai_costs_cents"] += amount_cents
                elif service.lower() in ["semrush"]:
                    cost_data["semrush_costs_cents"] += amount_cents
                elif service.lower() in ["gpu", "compute"]:
                    cost_data["gpu_costs_cents"] += amount_cents
                else:
                    cost_data["other_api_costs_cents"] += amount_cents

            return cost_data

        except Exception as e:
            logger.error(f"Error querying cost tracker database for {date}: {e}")
            return {}

    def _store_daily_aggregation(self, data: Dict[str, Any]) -> None:
        """Store daily aggregation data in database.

        Args:
            data: Aggregated data dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO daily_cost_revenue_summary (
                        date, gross_revenue_cents, net_revenue_cents, stripe_fees_cents,
                        tax_amount_cents, transaction_count, refund_count, refund_amount_cents,
                        total_operational_costs_cents, openai_costs_cents, semrush_costs_cents,
                        gpu_costs_cents, other_api_costs_cents, gross_profit_cents,
                        net_profit_cents, gross_margin_percent, net_margin_percent,
                        last_updated, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["date"],
                        data["gross_revenue_cents"],
                        data["net_revenue_cents"],
                        data["stripe_fees_cents"],
                        data["tax_amount_cents"],
                        data["transaction_count"],
                        data["refund_count"],
                        data["refund_amount_cents"],
                        data["total_operational_costs_cents"],
                        data["openai_costs_cents"],
                        data["semrush_costs_cents"],
                        data["gpu_costs_cents"],
                        data["other_api_costs_cents"],
                        data["gross_profit_cents"],
                        data["net_profit_cents"],
                        data["gross_margin_percent"],
                        data["net_margin_percent"],
                        data["last_updated"],
                        data.get("created_at", data["last_updated"]),
                    ),
                )

                conn.commit()

            finally:
                conn.close()

    def aggregate_monthly_data(self, year: int, month: int) -> Dict[str, Any]:
        """Aggregate cost and revenue data for a specific month.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Aggregated monthly data dictionary
        """
        logger.info(f"Aggregating monthly data for {year}-{month:02d}")

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
                        SUM(gross_revenue_cents) as total_gross_revenue,
                        SUM(net_revenue_cents) as total_net_revenue,
                        SUM(stripe_fees_cents) as total_stripe_fees,
                        SUM(tax_amount_cents) as total_tax,
                        SUM(transaction_count) as total_transactions,
                        SUM(refund_count) as total_refunds,
                        SUM(refund_amount_cents) as total_refund_amount,
                        SUM(total_operational_costs_cents) as total_costs,
                        SUM(openai_costs_cents) as total_openai_costs,
                        SUM(semrush_costs_cents) as total_semrush_costs,
                        SUM(gpu_costs_cents) as total_gpu_costs,
                        SUM(other_api_costs_cents) as total_other_costs,
                        COUNT(*) as active_days
                    FROM daily_cost_revenue_summary
                    WHERE date >= ? AND date < ?
                """,
                    (start_date, end_date),
                )

                result = cursor.fetchone()

                if result and result[0] is not None:
                    (
                        total_gross_revenue,
                        total_net_revenue,
                        total_stripe_fees,
                        total_tax,
                        total_transactions,
                        total_refunds,
                        total_refund_amount,
                        total_costs,
                        total_openai_costs,
                        total_semrush_costs,
                        total_gpu_costs,
                        total_other_costs,
                        active_days,
                    ) = result

                    # Calculate profit metrics
                    gross_profit_cents = (total_gross_revenue or 0) - (total_costs or 0)
                    net_profit_cents = (total_net_revenue or 0) - (total_costs or 0)

                    gross_margin_percent = (
                        (gross_profit_cents / (total_gross_revenue or 1) * 100)
                        if total_gross_revenue > 0
                        else 0
                    )
                    net_margin_percent = (
                        (net_profit_cents / (total_net_revenue or 1) * 100)
                        if total_net_revenue > 0
                        else 0
                    )

                    monthly_data = {
                        "year": year,
                        "month": month,
                        "gross_revenue_cents": total_gross_revenue or 0,
                        "net_revenue_cents": total_net_revenue or 0,
                        "stripe_fees_cents": total_stripe_fees or 0,
                        "tax_amount_cents": total_tax or 0,
                        "transaction_count": total_transactions or 0,
                        "refund_count": total_refunds or 0,
                        "refund_amount_cents": total_refund_amount or 0,
                        "total_operational_costs_cents": total_costs or 0,
                        "openai_costs_cents": total_openai_costs or 0,
                        "semrush_costs_cents": total_semrush_costs or 0,
                        "gpu_costs_cents": total_gpu_costs or 0,
                        "other_api_costs_cents": total_other_costs or 0,
                        "gross_profit_cents": gross_profit_cents,
                        "net_profit_cents": net_profit_cents,
                        "gross_margin_percent": gross_margin_percent,
                        "net_margin_percent": net_margin_percent,
                        "active_days": active_days or 0,
                        "last_updated": datetime.now().isoformat(),
                        "created_at": datetime.now().isoformat(),
                    }

                    # Store monthly aggregation
                    self._store_monthly_aggregation_unlocked(monthly_data)

                    logger.info(
                        f"Monthly aggregation completed for {year}-{month:02d}: "
                        f"revenue=${(total_gross_revenue or 0)/100:.2f}, "
                        f"costs=${(total_costs or 0)/100:.2f}, "
                        f"profit=${gross_profit_cents/100:.2f}"
                    )

                    return monthly_data

            finally:
                conn.close()

        return {}

    def _store_monthly_aggregation(self, data: Dict[str, Any]) -> None:
        """Store monthly aggregation data in database.

        Args:
            data: Monthly aggregated data dictionary
        """
        with self._lock:
            self._store_monthly_aggregation_unlocked(data)

    def _store_monthly_aggregation_unlocked(self, data: Dict[str, Any]) -> None:
        """Store monthly aggregation data in database without acquiring lock.

        Args:
            data: Monthly aggregated data dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO monthly_cost_revenue_summary (
                    year, month, gross_revenue_cents, net_revenue_cents, stripe_fees_cents,
                    tax_amount_cents, transaction_count, refund_count, refund_amount_cents,
                    total_operational_costs_cents, openai_costs_cents, semrush_costs_cents,
                    gpu_costs_cents, other_api_costs_cents, gross_profit_cents,
                    net_profit_cents, gross_margin_percent, net_margin_percent,
                    active_days, last_updated, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["year"],
                    data["month"],
                    data["gross_revenue_cents"],
                    data["net_revenue_cents"],
                    data["stripe_fees_cents"],
                    data["tax_amount_cents"],
                    data["transaction_count"],
                    data["refund_count"],
                    data["refund_amount_cents"],
                    data["total_operational_costs_cents"],
                    data["openai_costs_cents"],
                    data["semrush_costs_cents"],
                    data["gpu_costs_cents"],
                    data["other_api_costs_cents"],
                    data["gross_profit_cents"],
                    data["net_profit_cents"],
                    data["gross_margin_percent"],
                    data["net_margin_percent"],
                    data["active_days"],
                    data["last_updated"],
                    data.get("created_at", data["last_updated"]),
                ),
            )

            conn.commit()

        finally:
            conn.close()

    def get_daily_summary(self, date: str) -> Optional[Dict[str, Any]]:
        """Get daily cost and revenue summary.

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
                    SELECT * FROM daily_cost_revenue_summary WHERE date = ?
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

    def get_monthly_summary(self, year: int, month: int) -> Optional[Dict[str, Any]]:
        """Get monthly cost and revenue summary.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Monthly summary data or None
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    SELECT * FROM monthly_cost_revenue_summary WHERE year = ? AND month = ?
                """,
                    (year, month),
                )

                result = cursor.fetchone()
                if result:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, result))
                return None

            finally:
                conn.close()

    def get_grafana_dashboard_data(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Get data formatted for Grafana dashboard.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Dashboard data dictionary
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    SELECT
                        date,
                        gross_revenue_cents / 100.0 as gross_revenue,
                        net_revenue_cents / 100.0 as net_revenue,
                        stripe_fees_cents / 100.0 as stripe_fees,
                        total_operational_costs_cents / 100.0 as total_costs,
                        gross_profit_cents / 100.0 as gross_profit,
                        net_profit_cents / 100.0 as net_profit,
                        gross_margin_percent,
                        net_margin_percent,
                        transaction_count
                    FROM daily_cost_revenue_summary
                    WHERE date >= ? AND date <= ?
                    ORDER BY date
                """,
                    (start_date, end_date),
                )

                results = cursor.fetchall()

                # Format data for Grafana
                dashboard_data = {
                    "time_series": [],
                    "summary": {
                        "total_gross_revenue": 0,
                        "total_net_revenue": 0,
                        "total_stripe_fees": 0,
                        "total_costs": 0,
                        "total_gross_profit": 0,
                        "total_net_profit": 0,
                        "avg_gross_margin": 0,
                        "avg_net_margin": 0,
                        "total_transactions": 0,
                    },
                }

                for row in results:
                    (
                        date,
                        gross_revenue,
                        net_revenue,
                        stripe_fees,
                        total_costs,
                        gross_profit,
                        net_profit,
                        gross_margin,
                        net_margin,
                        transactions,
                    ) = row

                    dashboard_data["time_series"].append(
                        {
                            "date": date,
                            "gross_revenue": gross_revenue,
                            "net_revenue": net_revenue,
                            "stripe_fees": stripe_fees,
                            "total_costs": total_costs,
                            "gross_profit": gross_profit,
                            "net_profit": net_profit,
                            "gross_margin_percent": gross_margin,
                            "net_margin_percent": net_margin,
                            "transaction_count": transactions,
                        }
                    )

                    # Update summary
                    dashboard_data["summary"]["total_gross_revenue"] += gross_revenue
                    dashboard_data["summary"]["total_net_revenue"] += net_revenue
                    dashboard_data["summary"]["total_stripe_fees"] += stripe_fees
                    dashboard_data["summary"]["total_costs"] += total_costs
                    dashboard_data["summary"]["total_gross_profit"] += gross_profit
                    dashboard_data["summary"]["total_net_profit"] += net_profit
                    dashboard_data["summary"]["total_transactions"] += transactions

                # Calculate average margins
                if results:
                    dashboard_data["summary"]["avg_gross_margin"] = sum(
                        row[7] for row in results
                    ) / len(results)
                    dashboard_data["summary"]["avg_net_margin"] = sum(
                        row[8] for row in results
                    ) / len(results)

                return dashboard_data

            finally:
                conn.close()


# Create singleton instance
cost_aggregation_service = CostAggregationService()
