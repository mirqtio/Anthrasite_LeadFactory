"""
Unit tests for the Report Template Engine.
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open

from leadfactory.services.report_template_engine import (
    ReportTemplateEngine,
    ReportData,
    ReportSection,
    format_financial_data,
    create_comparison_table,
    generate_executive_summary
)


class TestReportSection:
    """Test the ReportSection dataclass."""

    def test_report_section_creation(self):
        """Test creating a report section."""
        section = ReportSection(
            title="Test Section",
            content="Test content",
            section_type="text",
            order=1
        )

        assert section.title == "Test Section"
        assert section.content == "Test content"
        assert section.section_type == "text"
        assert section.order == 1
        assert section.metadata == {}

    def test_report_section_with_metadata(self):
        """Test creating a report section with metadata."""
        metadata = {"priority": "high", "category": "summary"}
        section = ReportSection(
            title="Test Section",
            content="Test content",
            metadata=metadata
        )

        assert section.metadata == metadata


class TestReportData:
    """Test the ReportData dataclass."""

    def test_report_data_creation(self):
        """Test creating report data."""
        report = ReportData(
            title="Test Report",
            subtitle="Test Subtitle",
            company_name="Test Company"
        )

        assert report.title == "Test Report"
        assert report.subtitle == "Test Subtitle"
        assert report.company_name == "Test Company"
        assert isinstance(report.report_date, datetime)
        assert report.sections == []
        assert report.metadata == {}

    def test_add_section(self):
        """Test adding sections to report data."""
        report = ReportData(title="Test Report")

        section1 = ReportSection("Section 1", "Content 1", order=2)
        section2 = ReportSection("Section 2", "Content 2", order=1)

        report.add_section(section1)
        report.add_section(section2)

        # Should be sorted by order
        assert len(report.sections) == 2
        assert report.sections[0].title == "Section 2"  # order=1
        assert report.sections[1].title == "Section 1"  # order=2

    def test_get_section(self):
        """Test getting a section by title."""
        report = ReportData(title="Test Report")
        section = ReportSection("Test Section", "Content")
        report.add_section(section)

        found_section = report.get_section("Test Section")
        assert found_section is not None
        assert found_section.title == "Test Section"

        not_found = report.get_section("Non-existent Section")
        assert not_found is None


class TestReportTemplateEngine:
    """Test the ReportTemplateEngine class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.engine = ReportTemplateEngine(template_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_engine_initialization(self):
        """Test template engine initialization."""
        assert self.engine.template_dir == Path(self.temp_dir)
        assert self.engine.env is not None

        # Check that default templates were created
        assert (Path(self.temp_dir) / "audit_report.html").exists()
        assert (Path(self.temp_dir) / "table_section.html").exists()
        assert (Path(self.temp_dir) / "chart_section.html").exists()
        assert (Path(self.temp_dir) / "styles.css").exists()

    def test_custom_filters(self):
        """Test custom Jinja2 filters."""
        # Test format_currency filter
        template_str = "{{ 1234.56 | format_currency }}"
        template = self.engine.env.from_string(template_str)
        result = template.render()
        assert result == "$1,234.56"

        # Test format_percentage filter
        template_str = "{{ 0.1234 | format_percentage }}"
        template = self.engine.env.from_string(template_str)
        result = template.render()
        assert result == "12.3%"

        # Test format_date filter
        test_date = datetime(2023, 12, 25, 15, 30, 0)
        template_str = "{{ test_date | format_date }}"
        template = self.engine.env.from_string(template_str)
        result = template.render(test_date=test_date)
        assert "December 25, 2023" in result

        # Test truncate_text filter
        template_str = "{{ 'This is a very long text that should be truncated' | truncate_text(20) }}"
        template = self.engine.env.from_string(template_str)
        result = template.render()
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    def test_render_simple_report(self):
        """Test rendering a simple report."""
        report = ReportData(
            title="Test Report",
            subtitle="Test Subtitle",
            company_name="Test Company"
        )

        section = ReportSection(
            title="Test Section",
            content="This is test content.",
            section_type="text",
            order=1
        )
        report.add_section(section)

        html_content = self.engine.render_report(report)

        assert "Test Report" in html_content
        assert "Test Subtitle" in html_content
        assert "Test Company" in html_content
        assert "Test Section" in html_content
        assert "This is test content." in html_content

    def test_render_report_with_table(self):
        """Test rendering a report with table section."""
        report = ReportData(title="Test Report")

        table_data = {
            "headers": ["Name", "Value"],
            "rows": [
                ["Item 1", "100"],
                ["Item 2", "200"]
            ]
        }

        section = ReportSection(
            title="Table Section",
            content=table_data,
            section_type="table",
            order=1
        )
        report.add_section(section)

        html_content = self.engine.render_report(report)

        assert "Table Section" in html_content
        assert "Name" in html_content
        assert "Value" in html_content
        assert "Item 1" in html_content
        assert "100" in html_content

    def test_render_report_with_list(self):
        """Test rendering a report with list section."""
        report = ReportData(title="Test Report")

        list_items = ["Item 1", "Item 2", "Item 3"]

        section = ReportSection(
            title="List Section",
            content=list_items,
            section_type="list",
            order=1
        )
        report.add_section(section)

        html_content = self.engine.render_report(report)

        assert "List Section" in html_content
        assert "Item 1" in html_content
        assert "Item 2" in html_content
        assert "Item 3" in html_content
        assert "<ul" in html_content
        assert "<li>" in html_content

    def test_render_report_with_chart(self):
        """Test rendering a report with chart section."""
        report = ReportData(title="Test Report")

        chart_data = {
            "chart_type": "bar",
            "data": [
                {"label": "Category A", "value": 85},
                {"label": "Category B", "value": 65}
            ],
            "max_value": 100
        }

        section = ReportSection(
            title="Chart Section",
            content=chart_data,
            section_type="chart",
            order=1
        )
        report.add_section(section)

        html_content = self.engine.render_report(report)

        assert "Chart Section" in html_content
        assert "Category A" in html_content
        assert "Category B" in html_content
        assert "bar-chart" in html_content

    def test_create_sample_report(self):
        """Test creating a sample report."""
        report = self.engine.create_sample_report()

        assert report.title == "Lead Generation Audit Report"
        assert report.subtitle == "Comprehensive Analysis and Recommendations"
        assert report.company_name == "Anthrasite Lead Factory"
        assert len(report.sections) > 0
        assert report.metadata.get("confidential") is True

        # Check that sections are properly ordered
        orders = [section.order for section in report.sections]
        assert orders == sorted(orders)

    def test_get_available_templates(self):
        """Test getting available templates."""
        templates = self.engine.get_available_templates()

        assert "audit_report.html" in templates
        assert "table_section.html" in templates
        assert "chart_section.html" in templates

    def test_render_with_missing_template(self):
        """Test rendering with a missing template."""
        report = ReportData(title="Test Report")

        with pytest.raises(Exception):
            self.engine.render_report(report, "non_existent_template.html")

    def test_render_with_confidential_metadata(self):
        """Test rendering report with confidential metadata."""
        report = ReportData(
            title="Confidential Report",
            metadata={"confidential": True}
        )

        html_content = self.engine.render_report(report)

        assert "CONFIDENTIAL" in html_content
        assert "For Internal Use Only" in html_content


class TestHelperFunctions:
    """Test helper functions."""

    def test_format_financial_data(self):
        """Test formatting financial data."""
        data = {
            "revenue": 1234567.89,
            "costs": 987654.32,
            "profit": 246913.57
        }

        formatted = format_financial_data(data)

        assert formatted["revenue"] == "$1,234,567.89"
        assert formatted["costs"] == "$987,654.32"
        assert formatted["profit"] == "$246,913.57"

    def test_format_financial_data_different_currency(self):
        """Test formatting financial data with different currency."""
        data = {"amount": 1000.50}

        formatted = format_financial_data(data, currency="EUR")

        assert formatted["amount"] == "1,000.50 EUR"

    def test_create_comparison_table(self):
        """Test creating a comparison table."""
        before = {"metric1": 100, "metric2": 200, "metric3": "old_value"}
        after = {"metric1": 120, "metric2": 180, "metric3": "new_value"}

        table = create_comparison_table(before, after, "Before", "After")

        assert table["headers"] == ["Metric", "Before", "After", "Change"]
        assert len(table["rows"]) == 3

        # Check metric1 (increase)
        metric1_row = next(row for row in table["rows"] if row[0] == "metric1")
        assert metric1_row[1] == "100"
        assert metric1_row[2] == "120"
        assert "+20.0%" in metric1_row[3]

        # Check metric2 (decrease)
        metric2_row = next(row for row in table["rows"] if row[0] == "metric2")
        assert metric2_row[1] == "200"
        assert metric2_row[2] == "180"
        assert "-10.0%" in metric2_row[3]

        # Check metric3 (text change)
        metric3_row = next(row for row in table["rows"] if row[0] == "metric3")
        assert metric3_row[1] == "old_value"
        assert metric3_row[2] == "new_value"
        assert metric3_row[3] == "Changed"

    def test_create_comparison_table_zero_division(self):
        """Test comparison table with zero values."""
        before = {"metric": 0}
        after = {"metric": 10}

        table = create_comparison_table(before, after)

        metric_row = table["rows"][0]
        assert metric_row[3] == "N/A"  # Should handle division by zero

    def test_generate_executive_summary(self):
        """Test generating executive summary."""
        metrics = {
            "conversion_rate": 2.5,
            "cost_per_lead": 45.20,
            "lead_volume": 1250
        }
        recommendations = [
            "Optimize landing pages",
            "Improve lead scoring",
            "Implement automation"
        ]

        summary = generate_executive_summary(metrics, recommendations)

        assert len(summary) >= 3
        assert "3 key performance indicators" in summary[0]
        assert "3 actionable recommendations" in summary[0]
        assert any("conversion rate" in item.lower() for item in summary)

    def test_generate_executive_summary_high_conversion(self):
        """Test executive summary with high conversion rate."""
        metrics = {"conversion_rate": 6.5}
        recommendations = ["Maintain current performance"]

        summary = generate_executive_summary(metrics, recommendations)

        # Should mention strong conversion rate
        assert any("strong conversion rate" in item.lower() for item in summary)


class TestTemplateIntegration:
    """Integration tests for template rendering."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.engine = ReportTemplateEngine(template_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_full_report_rendering(self):
        """Test rendering a complete report with all section types."""
        report = ReportData(
            title="Complete Test Report",
            subtitle="All Section Types",
            company_name="Test Corp",
            metadata={"confidential": True}
        )

        # Text section
        report.add_section(ReportSection(
            title="Summary",
            content=["First paragraph.", "Second paragraph."],
            section_type="text",
            order=1
        ))

        # List section
        report.add_section(ReportSection(
            title="Action Items",
            content=["Action 1", "Action 2", "Action 3"],
            section_type="list",
            order=2
        ))

        # Table section
        report.add_section(ReportSection(
            title="Metrics",
            content={
                "headers": ["Metric", "Value"],
                "rows": [["KPI 1", "100"], ["KPI 2", "200"]]
            },
            section_type="table",
            order=3
        ))

        # Chart section
        report.add_section(ReportSection(
            title="Performance",
            content={
                "chart_type": "bar",
                "data": [{"label": "Q1", "value": 75}],
                "max_value": 100
            },
            section_type="chart",
            order=4
        ))

        html_content = self.engine.render_report(report)

        # Verify all content is present
        assert "Complete Test Report" in html_content
        assert "All Section Types" in html_content
        assert "Test Corp" in html_content
        assert "CONFIDENTIAL" in html_content

        # Verify sections
        assert "Summary" in html_content
        assert "First paragraph." in html_content
        assert "Action Items" in html_content
        assert "Action 1" in html_content
        assert "Metrics" in html_content
        assert "KPI 1" in html_content
        assert "Performance" in html_content
        assert "Q1" in html_content

        # Verify HTML structure
        assert "<html" in html_content
        assert "</html>" in html_content
        assert "report-container" in html_content
        assert "section-title" in html_content
