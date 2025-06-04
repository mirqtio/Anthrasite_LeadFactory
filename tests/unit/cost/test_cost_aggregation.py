"""
Unit tests for Cost Aggregation Service
======================================

Tests the cost aggregation service that combines operational costs
with financial tracking data for comprehensive profit analysis.
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from leadfactory.cost.cost_aggregation import CostAggregationService


class TestCostAggregationService(unittest.TestCase):
    """Test cost aggregation service functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_cost_aggregation.db")

        # Create service instance
        self.service = CostAggregationService(db_path=self.db_path)

        # Mock tracking services
        self.mock_cost_tracker = Mock()
        self.mock_financial_tracker = Mock()

        self.service.cost_tracker = self.mock_cost_tracker
        self.service.financial_tracker = self.mock_financial_tracker

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_initialization(self):
        """Test that database tables are created properly."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check daily summary table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='daily_cost_revenue_summary'
        """)
        self.assertIsNotNone(cursor.fetchone())

        # Check monthly summary table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='monthly_cost_revenue_summary'
        """)
        self.assertIsNotNone(cursor.fetchone())

        # Check indices exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_daily_summary_date'
        """)
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    def test_get_daily_financial_data(self):
        """Test getting daily financial data from financial tracker."""
        # Mock financial tracker response
        self.mock_financial_tracker.get_daily_summary.return_value = {
            "total_revenue_cents": 10000,
            "net_revenue_cents": 9500,
            "total_stripe_fees_cents": 300,
            "total_tax_cents": 200,
            "transaction_count": 5,
            "refund_count": 1,
            "refund_amount_cents": 500,
        }

        result = self.service._get_daily_financial_data("2024-01-15")

        expected = {
            "gross_revenue_cents": 10000,
            "net_revenue_cents": 9500,
            "stripe_fees_cents": 300,
            "tax_amount_cents": 200,
            "transaction_count": 5,
            "refund_count": 1,
            "refund_amount_cents": 500,
        }

        self.assertEqual(result, expected)
        self.mock_financial_tracker.get_daily_summary.assert_called_once_with(
            "2024-01-15"
        )

    def test_get_daily_financial_data_no_data(self):
        """Test getting daily financial data when no data exists."""
        self.mock_financial_tracker.get_daily_summary.return_value = None

        result = self.service._get_daily_financial_data("2024-01-15")

        self.assertEqual(result, {})

    def test_get_daily_financial_data_error_handling(self):
        """Test error handling in financial data retrieval."""
        self.mock_financial_tracker.get_daily_summary.side_effect = Exception(
            "Database error"
        )

        result = self.service._get_daily_financial_data("2024-01-15")

        self.assertEqual(result, {})

    def test_query_cost_tracker_database(self):
        """Test querying cost tracker database directly."""
        # Create mock cost tracker database
        cost_db_path = str(Path(self.temp_dir) / "test_costs.db")
        self.mock_cost_tracker.db_path = cost_db_path

        # Create costs table and insert test data
        conn = sqlite3.connect(cost_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE costs (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                service TEXT,
                amount REAL
            )
        """)

        # Insert test cost data
        cursor.execute("""
            INSERT INTO costs (timestamp, service, amount) VALUES
            ('2024-01-15 10:00:00', 'openai', 5.50),
            ('2024-01-15 11:00:00', 'semrush', 2.25),
            ('2024-01-15 12:00:00', 'gpu', 1.75),
            ('2024-01-15 13:00:00', 'other_api', 0.50)
        """)

        conn.commit()
        conn.close()

        # Test the method
        result = self.service._query_cost_tracker_database("2024-01-15")

        expected = {
            "total_costs_cents": 1000,  # $10.00 total
            "openai_costs_cents": 550,  # $5.50
            "semrush_costs_cents": 225,  # $2.25
            "gpu_costs_cents": 175,  # $1.75
            "other_api_costs_cents": 50,  # $0.50
        }

        self.assertEqual(result, expected)

    def test_aggregate_daily_data(self):
        """Test daily data aggregation."""
        # Mock financial data
        self.mock_financial_tracker.get_daily_summary.return_value = {
            "total_revenue_cents": 15000,
            "net_revenue_cents": 14500,
            "total_stripe_fees_cents": 450,
            "total_tax_cents": 50,
            "transaction_count": 3,
            "refund_count": 0,
            "refund_amount_cents": 0,
        }

        # Mock cost data by setting up cost tracker database
        cost_db_path = str(Path(self.temp_dir) / "test_costs.db")
        self.mock_cost_tracker.db_path = cost_db_path

        conn = sqlite3.connect(cost_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE costs (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                service TEXT,
                amount REAL
            )
        """)
        cursor.execute("""
            INSERT INTO costs (timestamp, service, amount) VALUES
            ('2024-01-15 10:00:00', 'openai', 3.00)
        """)
        conn.commit()
        conn.close()

        # Test aggregation
        result = self.service.aggregate_daily_data("2024-01-15")

        # Verify calculations
        self.assertEqual(result["date"], "2024-01-15")
        self.assertEqual(result["gross_revenue_cents"], 15000)
        self.assertEqual(result["net_revenue_cents"], 14500)
        self.assertEqual(result["stripe_fees_cents"], 450)
        self.assertEqual(result["total_operational_costs_cents"], 300)  # $3.00
        self.assertEqual(result["gross_profit_cents"], 14700)  # 15000 - 300
        self.assertEqual(result["net_profit_cents"], 14200)  # 14500 - 300
        self.assertEqual(result["gross_margin_percent"], 98.0)  # (14700/15000)*100

        # Verify data was stored in database
        stored_data = self.service.get_daily_summary("2024-01-15")
        self.assertIsNotNone(stored_data)
        self.assertEqual(stored_data["gross_revenue_cents"], 15000)

    def test_aggregate_daily_data_no_revenue(self):
        """Test daily aggregation with no revenue data."""
        self.mock_financial_tracker.get_daily_summary.return_value = None
        self.mock_cost_tracker.db_path = str(Path(self.temp_dir) / "empty_costs.db")

        # Create empty costs database
        conn = sqlite3.connect(self.mock_cost_tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE costs (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                service TEXT,
                amount REAL
            )
        """)
        conn.commit()
        conn.close()

        result = self.service.aggregate_daily_data("2024-01-15")

        # Verify zero values
        self.assertEqual(result["gross_revenue_cents"], 0)
        self.assertEqual(result["net_revenue_cents"], 0)
        self.assertEqual(result["total_operational_costs_cents"], 0)
        self.assertEqual(result["gross_profit_cents"], 0)
        self.assertEqual(result["net_profit_cents"], 0)
        self.assertEqual(result["gross_margin_percent"], 0)

    def test_store_daily_aggregation(self):
        """Test storing daily aggregation data."""
        test_data = {
            "date": "2024-01-15",
            "gross_revenue_cents": 10000,
            "net_revenue_cents": 9500,
            "stripe_fees_cents": 300,
            "tax_amount_cents": 200,
            "transaction_count": 5,
            "refund_count": 1,
            "refund_amount_cents": 500,
            "total_operational_costs_cents": 1000,
            "openai_costs_cents": 800,
            "semrush_costs_cents": 200,
            "gpu_costs_cents": 0,
            "other_api_costs_cents": 0,
            "gross_profit_cents": 9000,
            "net_profit_cents": 8500,
            "gross_margin_percent": 90.0,
            "net_margin_percent": 89.47,
            "last_updated": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
        }

        self.service._store_daily_aggregation(test_data)

        # Verify data was stored
        stored_data = self.service.get_daily_summary("2024-01-15")
        self.assertIsNotNone(stored_data)
        self.assertEqual(stored_data["gross_revenue_cents"], 10000)
        self.assertEqual(stored_data["transaction_count"], 5)
        self.assertEqual(stored_data["gross_margin_percent"], 90.0)

    def test_aggregate_monthly_data(self):
        """Test monthly data aggregation."""
        # Insert some daily data first
        daily_data = [
            {
                "date": "2024-01-01",
                "gross_revenue_cents": 5000,
                "net_revenue_cents": 4800,
                "stripe_fees_cents": 150,
                "tax_amount_cents": 50,
                "transaction_count": 2,
                "refund_count": 0,
                "refund_amount_cents": 0,
                "total_operational_costs_cents": 500,
                "openai_costs_cents": 400,
                "semrush_costs_cents": 100,
                "gpu_costs_cents": 0,
                "other_api_costs_cents": 0,
                "gross_profit_cents": 4500,
                "net_profit_cents": 4300,
                "gross_margin_percent": 90.0,
                "net_margin_percent": 89.58,
                "last_updated": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
            },
            {
                "date": "2024-01-02",
                "gross_revenue_cents": 7500,
                "net_revenue_cents": 7200,
                "stripe_fees_cents": 225,
                "tax_amount_cents": 75,
                "transaction_count": 3,
                "refund_count": 1,
                "refund_amount_cents": 1000,
                "total_operational_costs_cents": 750,
                "openai_costs_cents": 600,
                "semrush_costs_cents": 150,
                "gpu_costs_cents": 0,
                "other_api_costs_cents": 0,
                "gross_profit_cents": 6750,
                "net_profit_cents": 6450,
                "gross_margin_percent": 90.0,
                "net_margin_percent": 89.58,
                "last_updated": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
            },
        ]

        for data in daily_data:
            self.service._store_daily_aggregation(data)

        # Test monthly aggregation
        result = self.service.aggregate_monthly_data(2024, 1)

        # Verify monthly totals
        self.assertEqual(result["year"], 2024)
        self.assertEqual(result["month"], 1)
        self.assertEqual(result["gross_revenue_cents"], 12500)  # 5000 + 7500
        self.assertEqual(result["net_revenue_cents"], 12000)  # 4800 + 7200
        self.assertEqual(result["transaction_count"], 5)  # 2 + 3
        self.assertEqual(result["total_operational_costs_cents"], 1250)  # 500 + 750
        self.assertEqual(result["gross_profit_cents"], 11250)  # 12500 - 1250
        self.assertEqual(result["active_days"], 2)

        # Verify data was stored
        stored_monthly = self.service.get_monthly_summary(2024, 1)
        self.assertIsNotNone(stored_monthly)
        self.assertEqual(stored_monthly["gross_revenue_cents"], 12500)

    def test_get_grafana_dashboard_data(self):
        """Test getting data formatted for Grafana dashboard."""
        # Insert test daily data
        daily_data = [
            {
                "date": "2024-01-01",
                "gross_revenue_cents": 10000,
                "net_revenue_cents": 9500,
                "stripe_fees_cents": 300,
                "tax_amount_cents": 200,
                "transaction_count": 5,
                "refund_count": 0,
                "refund_amount_cents": 0,
                "total_operational_costs_cents": 1000,
                "openai_costs_cents": 800,
                "semrush_costs_cents": 200,
                "gpu_costs_cents": 0,
                "other_api_costs_cents": 0,
                "gross_profit_cents": 9000,
                "net_profit_cents": 8500,
                "gross_margin_percent": 90.0,
                "net_margin_percent": 89.47,
                "last_updated": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
            }
        ]

        for data in daily_data:
            self.service._store_daily_aggregation(data)

        # Test dashboard data retrieval
        result = self.service.get_grafana_dashboard_data("2024-01-01", "2024-01-01")

        # Verify structure
        self.assertIn("time_series", result)
        self.assertIn("summary", result)

        # Verify time series data
        time_series = result["time_series"]
        self.assertEqual(len(time_series), 1)

        day_data = time_series[0]
        self.assertEqual(day_data["date"], "2024-01-01")
        self.assertEqual(day_data["gross_revenue"], 100.0)  # Converted to dollars
        self.assertEqual(day_data["stripe_fees"], 3.0)
        self.assertEqual(day_data["total_costs"], 10.0)
        self.assertEqual(day_data["gross_profit"], 90.0)

        # Verify summary data
        summary = result["summary"]
        self.assertEqual(summary["total_gross_revenue"], 100.0)
        self.assertEqual(summary["total_stripe_fees"], 3.0)
        self.assertEqual(summary["total_transactions"], 5)

    def test_get_daily_summary_not_found(self):
        """Test getting daily summary when data doesn't exist."""
        result = self.service.get_daily_summary("2024-01-15")
        self.assertIsNone(result)

    def test_get_monthly_summary_not_found(self):
        """Test getting monthly summary when data doesn't exist."""
        result = self.service.get_monthly_summary(2024, 1)
        self.assertIsNone(result)

    def test_cost_tracker_database_error_handling(self):
        """Test error handling when cost tracker database is unavailable."""
        self.mock_cost_tracker.db_path = "/nonexistent/path/costs.db"

        result = self.service._query_cost_tracker_database("2024-01-15")

        # Should return empty cost data
        expected = {
            "total_costs_cents": 0,
            "openai_costs_cents": 0,
            "semrush_costs_cents": 0,
            "gpu_costs_cents": 0,
            "other_api_costs_cents": 0,
        }

        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
