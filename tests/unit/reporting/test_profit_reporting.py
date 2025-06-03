"""
Unit tests for Profit Reporting Service
======================================

Tests the profit reporting service that generates comprehensive
business intelligence reports and trend analysis.
"""

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from leadfactory.reporting.profit_reporting import ProfitReportingService


class TestProfitReportingService(unittest.TestCase):
    """Test profit reporting service functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for reports
        self.temp_dir = tempfile.mkdtemp()

        # Mock cost aggregation service
        self.mock_aggregation_service = Mock()

        # Create reporting service instance
        self.service = ProfitReportingService(
            cost_aggregation_service=self.mock_aggregation_service,
            reports_dir=self.temp_dir
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_daily_report(self):
        """Test generating a daily profit report."""
        # Mock daily summary data
        mock_daily_data = {
            'date': '2024-01-15',
            'gross_revenue_cents': 15000,
            'net_revenue_cents': 14500,
            'stripe_fees_cents': 450,
            'tax_amount_cents': 50,
            'transaction_count': 3,
            'refund_count': 0,
            'refund_amount_cents': 0,
            'total_operational_costs_cents': 800,
            'openai_costs_cents': 600,
            'semrush_costs_cents': 200,
            'gpu_costs_cents': 0,
            'other_api_costs_cents': 0,
            'gross_profit_cents': 14200,
            'net_profit_cents': 13700,
            'gross_margin_percent': 94.67,
            'net_margin_percent': 91.33
        }

        self.mock_aggregation_service.get_daily_summary.return_value = mock_daily_data

        # Generate report
        report = self.service.generate_daily_report('2024-01-15')

        # Verify report structure
        self.assertEqual(report['report_type'], 'daily')
        self.assertEqual(report['date'], '2024-01-15')
        self.assertIn('generated_at', report)

        # Verify revenue section
        self.assertEqual(report['revenue']['gross_revenue'], 150.0)
        self.assertEqual(report['revenue']['net_revenue'], 145.0)
        self.assertEqual(report['revenue']['stripe_fees'], 4.5)
        self.assertEqual(report['revenue']['transaction_count'], 3)

        # Verify costs section
        self.assertEqual(report['costs']['total_operational_costs'], 8.0)
        self.assertEqual(report['costs']['openai_costs'], 6.0)
        self.assertEqual(report['costs']['semrush_costs'], 2.0)

        # Verify profit section
        self.assertEqual(report['profit']['gross_profit'], 142.0)
        self.assertEqual(report['profit']['net_profit'], 137.0)
        self.assertAlmostEqual(report['profit']['gross_margin_percent'], 94.67, places=2)

        # Verify metrics section
        self.assertIn('metrics', report)
        self.assertAlmostEqual(report['metrics']['average_transaction_value'], 50.0, places=2)
        self.assertAlmostEqual(report['metrics']['cost_per_transaction'], 2.67, places=2)

        # Verify the service was called correctly
        self.mock_aggregation_service.get_daily_summary.assert_called_once_with('2024-01-15')

    def test_generate_daily_report_no_data(self):
        """Test generating daily report when no data exists."""
        self.mock_aggregation_service.get_daily_summary.return_value = None

        report = self.service.generate_daily_report('2024-01-15')

        # Verify empty report structure
        self.assertEqual(report['report_type'], 'daily')
        self.assertEqual(report['date'], '2024-01-15')

        # Verify zero values
        self.assertEqual(report['revenue']['gross_revenue'], 0.0)
        self.assertEqual(report['costs']['total_operational_costs'], 0.0)
        self.assertEqual(report['profit']['gross_profit'], 0.0)

        # Verify insights
        self.assertIn('No data available', report['insights'][0])

    def test_generate_weekly_report(self):
        """Test generating a weekly profit report."""
        # Mock daily data for a week
        mock_daily_data = []
        for i in range(7):
            date = datetime(2024, 1, 15) + timedelta(days=i)
            mock_daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'gross_revenue_cents': 10000 + (i * 1000),
                'net_revenue_cents': 9500 + (i * 950),
                'stripe_fees_cents': 300 + (i * 30),
                'tax_amount_cents': 200,
                'transaction_count': 5 + i,
                'refund_count': 0,
                'refund_amount_cents': 0,
                'total_operational_costs_cents': 500 + (i * 50),
                'openai_costs_cents': 400 + (i * 40),
                'semrush_costs_cents': 100 + (i * 10),
                'gpu_costs_cents': 0,
                'other_api_costs_cents': 0,
                'gross_profit_cents': 9500 + (i * 950),
                'net_profit_cents': 9000 + (i * 900),
                'gross_margin_percent': 95.0,
                'net_margin_percent': 90.0
            })

        def mock_get_daily_summary(date):
            for data in mock_daily_data:
                if data['date'] == date:
                    return data
            return None

        self.mock_aggregation_service.get_daily_summary.side_effect = mock_get_daily_summary

        # Generate weekly report
        report = self.service.generate_weekly_report('2024-01-15')

        # Verify report structure
        self.assertEqual(report['report_type'], 'weekly')
        self.assertEqual(report['start_date'], '2024-01-15')
        self.assertEqual(report['end_date'], '2024-01-21')

        # Verify aggregated totals
        revenue = report['revenue']
        self.assertEqual(revenue['gross_revenue'], 910.0)  # Sum of daily revenues
        self.assertEqual(revenue['transaction_count'], 56)  # Sum of transactions

        # Verify daily breakdown exists
        self.assertIn('daily_breakdown', report)
        self.assertEqual(len(report['daily_breakdown']), 7)

        # Verify first day breakdown
        first_day = report['daily_breakdown'][0]
        self.assertEqual(first_day['date'], '2024-01-15')
        self.assertEqual(first_day['gross_revenue'], 100.0)

    def test_generate_monthly_report(self):
        """Test generating a monthly profit report."""
        # Mock monthly summary data
        mock_monthly_data = {
            'year': 2024,
            'month': 1,
            'gross_revenue_cents': 500000,
            'net_revenue_cents': 475000,
            'stripe_fees_cents': 15000,
            'tax_amount_cents': 10000,
            'transaction_count': 150,
            'refund_count': 5,
            'refund_amount_cents': 5000,
            'total_operational_costs_cents': 25000,
            'openai_costs_cents': 20000,
            'semrush_costs_cents': 5000,
            'gpu_costs_cents': 0,
            'other_api_costs_cents': 0,
            'gross_profit_cents': 475000,
            'net_profit_cents': 450000,
            'gross_margin_percent': 95.0,
            'net_margin_percent': 90.0,
            'active_days': 31
        }

        self.mock_aggregation_service.get_monthly_summary.return_value = mock_monthly_data

        # Generate monthly report
        report = self.service.generate_monthly_report(2024, 1)

        # Verify report structure
        self.assertEqual(report['report_type'], 'monthly')
        self.assertEqual(report['year'], 2024)
        self.assertEqual(report['month'], 1)

        # Verify revenue metrics
        revenue = report['revenue']
        self.assertEqual(revenue['gross_revenue'], 5000.0)
        self.assertEqual(revenue['transaction_count'], 150)

        # Verify profit metrics
        profit = report['profit']
        self.assertEqual(profit['gross_profit'], 4750.0)
        self.assertEqual(profit['net_profit'], 4500.0)

        # Verify monthly specific metrics
        self.assertEqual(report['active_days'], 31)
        self.assertEqual(report['average_daily_revenue'], 161.29)  # 5000/31
        self.assertEqual(report['average_daily_profit'], 145.16)   # 4500/31

    def test_analyze_trends(self):
        """Test trend analysis functionality."""
        # Mock historical data for trend analysis
        mock_data = []
        for i in range(30):  # 30 days of data
            date = datetime(2024, 1, 1) + timedelta(days=i)
            mock_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'gross_revenue_cents': 10000 + (i * 100),  # Increasing trend
                'net_revenue_cents': 9500 + (i * 95),
                'total_operational_costs_cents': 1000 + (i * 10),  # Increasing costs
                'gross_profit_cents': 9000 + (i * 90),
                'net_profit_cents': 8500 + (i * 85),
                'transaction_count': 10 + i,
                'gross_margin_percent': 90.0,
                'net_margin_percent': 85.0
            })

        def mock_get_daily_summary(date):
            for data in mock_data:
                if data['date'] == date:
                    return data
            return None

        self.mock_aggregation_service.get_daily_summary.side_effect = mock_get_daily_summary

        # Analyze trends
        trends = self.service.analyze_trends('2024-01-01', '2024-01-30')

        # Verify trend structure
        self.assertIn('revenue_trend', trends)
        self.assertIn('cost_trend', trends)
        self.assertIn('profit_trend', trends)
        self.assertIn('transaction_trend', trends)

        # Verify revenue trend (should be positive)
        revenue_trend = trends['revenue_trend']
        self.assertGreater(revenue_trend['slope'], 0)
        self.assertGreater(revenue_trend['correlation'], 0.9)  # Strong positive correlation
        self.assertEqual(revenue_trend['direction'], 'increasing')

        # Verify cost trend (should be positive)
        cost_trend = trends['cost_trend']
        self.assertGreater(cost_trend['slope'], 0)
        self.assertEqual(cost_trend['direction'], 'increasing')

        # Verify profit trend (should be positive)
        profit_trend = trends['profit_trend']
        self.assertGreater(profit_trend['slope'], 0)
        self.assertEqual(profit_trend['direction'], 'increasing')

    def test_generate_business_insights(self):
        """Test business insights generation."""
        # Mock report data
        mock_report = {
            'revenue': {
                'gross_revenue': 1000.0,
                'net_revenue': 950.0,
                'stripe_fees': 30.0,
                'transaction_count': 50,
                'refund_count': 2,
                'refund_amount': 20.0
            },
            'costs': {
                'total_operational_costs': 100.0,
                'openai_costs': 80.0,
                'semrush_costs': 20.0
            },
            'profit': {
                'gross_profit': 900.0,
                'net_profit': 850.0,
                'gross_margin_percent': 90.0,
                'net_margin_percent': 85.0
            }
        }

        insights = self.service._generate_business_insights(mock_report)

        # Verify insights are generated
        self.assertIsInstance(insights, list)
        self.assertGreater(len(insights), 0)

        # Check for specific insight types
        insight_text = ' '.join(insights)

        # Should mention high margin
        self.assertIn('margin', insight_text.lower())

        # Should mention OpenAI as primary cost
        self.assertIn('openai', insight_text.lower())

        # Should mention transaction metrics
        self.assertIn('transaction', insight_text.lower())

    def test_export_to_json(self):
        """Test exporting report to JSON format."""
        # Mock report data
        mock_report = {
            'report_type': 'daily',
            'date': '2024-01-15',
            'revenue': {'gross_revenue': 100.0},
            'costs': {'total_operational_costs': 10.0},
            'profit': {'gross_profit': 90.0}
        }

        # Export to JSON
        json_path = self.service.export_to_json(mock_report, 'test_report')

        # Verify file was created
        self.assertTrue(Path(json_path).exists())

        # Verify content
        with open(json_path, 'r') as f:
            loaded_data = json.load(f)

        self.assertEqual(loaded_data['report_type'], 'daily')
        self.assertEqual(loaded_data['revenue']['gross_revenue'], 100.0)

    def test_export_to_csv(self):
        """Test exporting report to CSV format."""
        # Mock report data with daily breakdown
        mock_report = {
            'report_type': 'weekly',
            'daily_breakdown': [
                {
                    'date': '2024-01-15',
                    'gross_revenue': 100.0,
                    'total_costs': 10.0,
                    'gross_profit': 90.0
                },
                {
                    'date': '2024-01-16',
                    'gross_revenue': 120.0,
                    'total_costs': 12.0,
                    'gross_profit': 108.0
                }
            ]
        }

        # Export to CSV
        csv_path = self.service.export_to_csv(mock_report, 'test_report')

        # Verify file was created
        self.assertTrue(Path(csv_path).exists())

        # Verify content
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['date'], '2024-01-15')
        self.assertEqual(float(rows[0]['gross_revenue']), 100.0)
        self.assertEqual(float(rows[1]['gross_revenue']), 120.0)

    def test_save_report(self):
        """Test saving report to disk."""
        # Mock report data
        mock_report = {
            'report_type': 'daily',
            'date': '2024-01-15',
            'revenue': {'gross_revenue': 100.0}
        }

        # Save report
        saved_path = self.service.save_report(mock_report, 'test_daily_report')

        # Verify file was created
        self.assertTrue(Path(saved_path).exists())

        # Verify it's a JSON file
        self.assertTrue(saved_path.endswith('.json'))

        # Verify content
        with open(saved_path, 'r') as f:
            loaded_data = json.load(f)

        self.assertEqual(loaded_data['report_type'], 'daily')

    def test_trend_analysis_insufficient_data(self):
        """Test trend analysis with insufficient data points."""
        # Mock minimal data (only 2 points)
        mock_data = [
            {
                'date': '2024-01-15',
                'gross_revenue_cents': 10000,
                'total_operational_costs_cents': 1000,
                'gross_profit_cents': 9000,
                'transaction_count': 10
            },
            {
                'date': '2024-01-16',
                'gross_revenue_cents': 11000,
                'total_operational_costs_cents': 1100,
                'gross_profit_cents': 9900,
                'transaction_count': 11
            }
        ]

        def mock_get_daily_summary(date):
            for data in mock_data:
                if data['date'] == date:
                    return data
            return None

        self.mock_aggregation_service.get_daily_summary.side_effect = mock_get_daily_summary

        # Analyze trends
        trends = self.service.analyze_trends('2024-01-15', '2024-01-16')

        # Should still return trend data but with limited confidence
        self.assertIn('revenue_trend', trends)
        self.assertIsNotNone(trends['revenue_trend']['slope'])

    def test_weekly_report_partial_week(self):
        """Test weekly report generation with partial week data."""
        # Mock data for only 3 days of the week
        mock_daily_data = []
        for i in range(3):
            date = datetime(2024, 1, 15) + timedelta(days=i)
            mock_daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'gross_revenue_cents': 10000,
                'net_revenue_cents': 9500,
                'total_operational_costs_cents': 500,
                'gross_profit_cents': 9500,
                'transaction_count': 5
            })

        def mock_get_daily_summary(date):
            for data in mock_daily_data:
                if data['date'] == date:
                    return data
            return None

        self.mock_aggregation_service.get_daily_summary.side_effect = mock_get_daily_summary

        # Generate weekly report
        report = self.service.generate_weekly_report('2024-01-15')

        # Should handle missing days gracefully
        self.assertEqual(report['report_type'], 'weekly')
        self.assertEqual(len(report['daily_breakdown']), 3)  # Only days with data

        # Revenue should be sum of available days
        self.assertEqual(report['revenue']['gross_revenue'], 300.0)  # 3 * 100


if __name__ == '__main__':
    unittest.main()
