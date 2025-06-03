"""
Tests for variant reporting module.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch

from leadfactory.pipeline.variant_reporting import (
    VariantReport, VariantComparison, StatisticalTest, VariantReporter
)
from leadfactory.pipeline.variant_tracking import VariantMetrics, VariantTracker, TrackingEvent, EventType


class TestVariantReport:
    """Test VariantReport class."""

    def test_variant_report_creation(self):
        """Test creating a variant report."""
        metrics = VariantMetrics(
            variant_id="variant123",
            total_assignments=100,
            pipeline_completions=80,
            emails_sent=75,
            emails_delivered=70,
            emails_opened=35,
            conversions=14
        )

        report = VariantReport(
            variant_id="variant123",
            variant_name="Test Variant",
            metrics=metrics,
            insights=["High conversion rate", "Good email engagement"],
            recommendations=["Continue testing", "Scale up"]
        )

        assert report.variant_id == "variant123"
        assert report.variant_name == "Test Variant"
        assert report.metrics == metrics
        assert len(report.insights) == 2
        assert len(report.recommendations) == 2

    def test_variant_report_serialization(self):
        """Test variant report serialization."""
        metrics = VariantMetrics(
            variant_id="variant123",
            total_assignments=100,
            pipeline_completions=80
        )

        report = VariantReport(
            variant_id="variant123",
            variant_name="Test Variant",
            metrics=metrics
        )

        data = report.to_dict()

        assert data["variant_id"] == "variant123"
        assert data["variant_name"] == "Test Variant"
        assert "metrics" in data
        assert "generated_at" in data


class TestStatisticalTest:
    """Test StatisticalTest class."""

    def test_statistical_test_creation(self):
        """Test creating a statistical test."""
        test = StatisticalTest(
            test_name="Z-test for proportions",
            statistic=2.5,
            p_value=0.012,
            significant=True,
            confidence_level=0.95,
            effect_size=0.15
        )

        assert test.test_name == "Z-test for proportions"
        assert test.statistic == 2.5
        assert test.p_value == 0.012
        assert test.significant is True
        assert test.confidence_level == 0.95
        assert test.effect_size == 0.15

    def test_statistical_test_serialization(self):
        """Test statistical test serialization."""
        test = StatisticalTest(
            test_name="T-test",
            statistic=1.96,
            p_value=0.05,
            significant=False
        )

        data = test.to_dict()

        assert data["test_name"] == "T-test"
        assert data["statistic"] == 1.96
        assert data["p_value"] == 0.05
        assert data["significant"] is False


class TestVariantComparison:
    """Test VariantComparison class."""

    def test_variant_comparison_creation(self):
        """Test creating a variant comparison."""
        metrics_a = VariantMetrics(
            variant_id="variant_a",
            total_assignments=100,
            conversions=10
        )

        metrics_b = VariantMetrics(
            variant_id="variant_b",
            total_assignments=100,
            conversions=15
        )

        test = StatisticalTest(
            test_name="Z-test",
            statistic=1.5,
            p_value=0.13,
            significant=False
        )

        comparison = VariantComparison(
            variant_a_id="variant_a",
            variant_b_id="variant_b",
            variant_a_name="Variant A",
            variant_b_name="Variant B",
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            statistical_tests=[test],
            insights=["B performs better"],
            recommendations=["Consider switching to B"]
        )

        assert comparison.variant_a_id == "variant_a"
        assert comparison.variant_b_id == "variant_b"
        assert len(comparison.statistical_tests) == 1
        assert len(comparison.insights) == 1

    def test_variant_comparison_serialization(self):
        """Test variant comparison serialization."""
        metrics_a = VariantMetrics(variant_id="a", total_assignments=50)
        metrics_b = VariantMetrics(variant_id="b", total_assignments=50)

        comparison = VariantComparison(
            variant_a_id="a",
            variant_b_id="b",
            variant_a_name="A",
            variant_b_name="B",
            metrics_a=metrics_a,
            metrics_b=metrics_b
        )

        data = comparison.to_dict()

        assert data["variant_a_id"] == "a"
        assert data["variant_b_id"] == "b"
        assert "metrics_a" in data
        assert "metrics_b" in data
        assert "generated_at" in data


class TestVariantReporter:
    """Test VariantReporter class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = VariantTracker(db_path=self.temp_db.name)
        self.reporter = VariantReporter(tracker=self.tracker)

        # Set up test data
        self._setup_test_data()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracker.close()
        os.unlink(self.temp_db.name)

    def _setup_test_data(self):
        """Set up test tracking data."""
        # Variant A: 100 assignments, 80 completions, 60 emails, 50 delivered, 25 opened, 10 conversions
        variant_a_events = []
        for i in range(100):
            variant_a_events.append(TrackingEvent("variant_a", 1000 + i, EventType.VARIANT_ASSIGNED))
            if i < 80:
                variant_a_events.append(TrackingEvent("variant_a", 1000 + i, EventType.PIPELINE_COMPLETED))
                if i < 60:
                    variant_a_events.append(TrackingEvent("variant_a", 1000 + i, EventType.EMAIL_SENT))
                    if i < 50:
                        variant_a_events.append(TrackingEvent("variant_a", 1000 + i, EventType.EMAIL_DELIVERED))
                        if i < 25:
                            variant_a_events.append(TrackingEvent("variant_a", 1000 + i, EventType.EMAIL_OPENED))
                            if i < 10:
                                variant_a_events.append(TrackingEvent("variant_a", 1000 + i, EventType.CONVERSION))

        # Variant B: 100 assignments, 85 completions, 70 emails, 65 delivered, 35 opened, 15 conversions
        variant_b_events = []
        for i in range(100):
            variant_b_events.append(TrackingEvent("variant_b", 2000 + i, EventType.VARIANT_ASSIGNED))
            if i < 85:
                variant_b_events.append(TrackingEvent("variant_b", 2000 + i, EventType.PIPELINE_COMPLETED))
                if i < 70:
                    variant_b_events.append(TrackingEvent("variant_b", 2000 + i, EventType.EMAIL_SENT))
                    if i < 65:
                        variant_b_events.append(TrackingEvent("variant_b", 2000 + i, EventType.EMAIL_DELIVERED))
                        if i < 35:
                            variant_b_events.append(TrackingEvent("variant_b", 2000 + i, EventType.EMAIL_OPENED))
                            if i < 15:
                                variant_b_events.append(TrackingEvent("variant_b", 2000 + i, EventType.CONVERSION))

        # Track all events
        all_events = variant_a_events + variant_b_events
        for event in all_events:
            self.tracker.track_event(event)

    def test_generate_summary_report(self):
        """Test generating a summary report."""
        report = self.reporter.generate_summary_report("variant_a", "Variant A")

        assert report is not None
        assert report.variant_id == "variant_a"
        assert report.variant_name == "Variant A"
        assert report.metrics.total_assignments == 100
        assert report.metrics.pipeline_completions == 80
        assert report.metrics.conversions == 10
        assert len(report.insights) > 0
        assert len(report.recommendations) > 0

    def test_generate_comparison_report(self):
        """Test generating a comparison report."""
        comparison = self.reporter.generate_comparison_report(
            "variant_a", "variant_b",
            "Variant A", "Variant B"
        )

        assert comparison is not None
        assert comparison.variant_a_id == "variant_a"
        assert comparison.variant_b_id == "variant_b"
        assert comparison.metrics_a.total_assignments == 100
        assert comparison.metrics_b.total_assignments == 100
        assert len(comparison.statistical_tests) > 0
        assert len(comparison.insights) > 0

    def test_z_test_for_proportions(self):
        """Test z-test for proportions."""
        # Test with known values
        result = self.reporter._z_test_for_proportions(
            successes_a=10, total_a=100,
            successes_b=15, total_b=100,
            confidence_level=0.95
        )

        assert result is not None
        assert result.test_name == "Z-test for proportions"
        assert isinstance(result.statistic, float)
        assert isinstance(result.p_value, float)
        assert isinstance(result.significant, bool)
        assert result.confidence_level == 0.95

    def test_t_test_for_means(self):
        """Test t-test for means."""
        values_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        values_b = [2.0, 3.0, 4.0, 5.0, 6.0]

        result = self.reporter._t_test_for_means(values_a, values_b)

        assert result is not None
        assert result.test_name == "Welch's t-test for means"
        assert isinstance(result.statistic, float)
        assert isinstance(result.p_value, float)
        assert isinstance(result.significant, bool)

    def test_generate_insights(self):
        """Test generating insights."""
        metrics_a = VariantMetrics(
            variant_id="variant_a",
            total_assignments=100,
            pipeline_completions=80,
            conversions=10
        )

        metrics_b = VariantMetrics(
            variant_id="variant_b",
            total_assignments=100,
            pipeline_completions=85,
            conversions=15
        )

        insights = self.reporter._generate_insights(metrics_a, metrics_b)

        assert len(insights) > 0
        assert any("conversion" in insight.lower() for insight in insights)

    def test_generate_recommendations(self):
        """Test generating recommendations."""
        metrics_a = VariantMetrics(
            variant_id="variant_a",
            total_assignments=100,
            pipeline_completions=80,
            conversions=10
        )

        metrics_b = VariantMetrics(
            variant_id="variant_b",
            total_assignments=100,
            pipeline_completions=85,
            conversions=15
        )

        statistical_tests = [
            StatisticalTest(
                test_name="Test",
                statistic=2.0,
                p_value=0.03,
                significant=True
            )
        ]

        recommendations = self.reporter._generate_recommendations(
            metrics_a, metrics_b, statistical_tests
        )

        assert len(recommendations) > 0

    def test_insufficient_sample_size(self):
        """Test handling of insufficient sample size."""
        # Clear existing data
        self.tracker.clear_old_events(cutoff_date=None)

        # Add minimal data
        event = TrackingEvent("variant_small", 1, EventType.VARIANT_ASSIGNED)
        self.tracker.track_event(event)

        report = self.reporter.generate_summary_report("variant_small", "Small Variant")

        assert report is not None
        assert any("sample size" in insight.lower() for insight in report.insights)

    def test_no_data_variant(self):
        """Test handling of variant with no data."""
        report = self.reporter.generate_summary_report("nonexistent", "Nonexistent")

        assert report is not None
        assert report.metrics.total_assignments == 0
        assert any("no data" in insight.lower() for insight in report.insights)


class TestVariantReporterIntegration:
    """Integration tests for variant reporter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = VariantTracker(db_path=self.temp_db.name)
        self.reporter = VariantReporter(tracker=self.tracker)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracker.close()
        os.unlink(self.temp_db.name)

    def test_full_reporting_workflow(self):
        """Test complete reporting workflow."""
        # Set up realistic test data
        variant_ids = ["control", "treatment"]

        for variant_id in variant_ids:
            base_business_id = 1000 if variant_id == "control" else 2000

            # Simulate different performance levels
            assignments = 200
            completion_rate = 0.8 if variant_id == "control" else 0.85
            conversion_rate = 0.1 if variant_id == "control" else 0.12

            for i in range(assignments):
                business_id = base_business_id + i

                # Track assignment
                self.tracker.track_event(
                    TrackingEvent(variant_id, business_id, EventType.VARIANT_ASSIGNED)
                )

                # Track completion based on rate
                if i < assignments * completion_rate:
                    self.tracker.track_event(
                        TrackingEvent(variant_id, business_id, EventType.PIPELINE_COMPLETED)
                    )

                    # Track email events
                    self.tracker.track_event(
                        TrackingEvent(variant_id, business_id, EventType.EMAIL_SENT)
                    )
                    self.tracker.track_event(
                        TrackingEvent(variant_id, business_id, EventType.EMAIL_DELIVERED)
                    )

                    # Track conversions based on rate
                    if i < assignments * conversion_rate:
                        self.tracker.track_event(
                            TrackingEvent(variant_id, business_id, EventType.CONVERSION)
                        )

        # Generate summary reports
        control_report = self.reporter.generate_summary_report("control", "Control Group")
        treatment_report = self.reporter.generate_summary_report("treatment", "Treatment Group")

        assert control_report.metrics.total_assignments == 200
        assert treatment_report.metrics.total_assignments == 200
        assert treatment_report.metrics.conversions > control_report.metrics.conversions

        # Generate comparison report
        comparison = self.reporter.generate_comparison_report(
            "control", "treatment",
            "Control Group", "Treatment Group"
        )

        assert comparison is not None
        assert len(comparison.statistical_tests) > 0
        assert len(comparison.insights) > 0
        assert len(comparison.recommendations) > 0

        # Test serialization
        control_data = control_report.to_dict()
        treatment_data = treatment_report.to_dict()
        comparison_data = comparison.to_dict()

        assert "metrics" in control_data
        assert "insights" in treatment_data
        assert "statistical_tests" in comparison_data

    def test_edge_cases(self):
        """Test edge cases in reporting."""
        # Test with zero conversions
        self.tracker.track_event(
            TrackingEvent("zero_conv", 1, EventType.VARIANT_ASSIGNED)
        )
        self.tracker.track_event(
            TrackingEvent("zero_conv", 1, EventType.EMAIL_DELIVERED)
        )

        report = self.reporter.generate_summary_report("zero_conv", "Zero Conversions")
        assert report.metrics.conversion_rate == 0.0

        # Test comparison with identical variants
        for i in range(50):
            for variant_id in ["identical_a", "identical_b"]:
                self.tracker.track_event(
                    TrackingEvent(variant_id, 3000 + i, EventType.VARIANT_ASSIGNED)
                )
                self.tracker.track_event(
                    TrackingEvent(variant_id, 3000 + i, EventType.CONVERSION)
                )

        comparison = self.reporter.generate_comparison_report(
            "identical_a", "identical_b",
            "Identical A", "Identical B"
        )

        assert comparison is not None
        # Should detect no significant difference
        conversion_tests = [t for t in comparison.statistical_tests
                          if "conversion" in t.test_name.lower()]
        if conversion_tests:
            assert not conversion_tests[0].significant
