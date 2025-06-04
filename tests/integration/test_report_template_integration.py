"""
Integration tests for Report Template Engine with PDF Generator.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from leadfactory.services.pdf_generator import PDFGenerator
from leadfactory.services.report_template_engine import (
    ReportTemplateEngine,
    ReportData,
    ReportSection
)


class TestReportTemplateIntegration:
    """Integration tests for template engine with PDF generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "templates"
        self.template_dir.mkdir()

        # Initialize PDF generator with template support
        self.pdf_generator = PDFGenerator(template_dir=str(self.template_dir))

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_template_engine_initialization(self):
        """Test that PDF generator initializes template engine correctly."""
        assert self.pdf_generator.template_engine is not None
        assert isinstance(self.pdf_generator.template_engine, ReportTemplateEngine)

        # Check that default templates were created
        assert (self.template_dir / "audit_report.html").exists()
        assert (self.template_dir / "styles.css").exists()

    def test_generate_sample_audit_report(self):
        """Test generating a sample audit report."""
        # Generate sample report as bytes
        pdf_bytes = self.pdf_generator.create_sample_audit_report(return_bytes=True)

        assert pdf_bytes is not None
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000  # Should be a substantial PDF
        assert pdf_bytes.startswith(b'%PDF')  # PDF header

    def test_generate_sample_audit_report_to_file(self):
        """Test generating a sample audit report to file."""
        output_path = Path(self.temp_dir) / "sample_report.pdf"

        result_path = self.pdf_generator.create_sample_audit_report(
            output_path=str(output_path)
        )

        assert result_path == str(output_path)
        assert output_path.exists()
        assert output_path.stat().st_size > 1000  # Should be a substantial file

        # Verify it's a valid PDF
        with open(output_path, 'rb') as f:
            header = f.read(4)
            assert header == b'%PDF'

    def test_generate_custom_report_from_template(self):
        """Test generating a custom report using template system."""
        # Create custom report data
        report = ReportData(
            title="Custom Integration Test Report",
            subtitle="Testing Template Integration",
            company_name="Test Company Ltd.",
            metadata={"confidential": True}
        )

        # Add various section types
        report.add_section(ReportSection(
            title="Executive Summary",
            content=[
                "This is a test report generated during integration testing.",
                "It demonstrates the integration between the template engine and PDF generator."
            ],
            section_type="text",
            order=1
        ))

        report.add_section(ReportSection(
            title="Key Metrics",
            content={
                "headers": ["Metric", "Value", "Status"],
                "rows": [
                    ["Test Coverage", "95%", "Excellent"],
                    ["Performance", "Fast", "Good"],
                    ["Integration", "Working", "Success"]
                ]
            },
            section_type="table",
            order=2
        ))

        report.add_section(ReportSection(
            title="Action Items",
            content=[
                "Complete integration testing",
                "Verify PDF generation quality",
                "Document template usage"
            ],
            section_type="list",
            order=3
        ))

        report.add_section(ReportSection(
            title="Performance Chart",
            content={
                "chart_type": "bar",
                "data": [
                    {"label": "Template Rendering", "value": 95},
                    {"label": "PDF Generation", "value": 88},
                    {"label": "Integration Tests", "value": 92}
                ],
                "max_value": 100
            },
            section_type="chart",
            order=4
        ))

        # Generate PDF
        pdf_bytes = self.pdf_generator.generate_report_from_template(
            report_data=report,
            return_bytes=True
        )

        assert pdf_bytes is not None
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 2000  # Should be substantial with all content
        assert pdf_bytes.startswith(b'%PDF')

    def test_template_html_rendering(self):
        """Test that template engine renders HTML correctly."""
        # Create test report
        report = ReportData(
            title="HTML Rendering Test",
            company_name="Test Corp"
        )

        report.add_section(ReportSection(
            title="Test Section",
            content="This is test content for HTML rendering.",
            section_type="text",
            order=1
        ))

        # Render HTML
        html_content = self.pdf_generator.template_engine.render_report(report)

        assert "HTML Rendering Test" in html_content
        assert "Test Corp" in html_content
        assert "Test Section" in html_content
        assert "This is test content" in html_content
        assert "<html" in html_content
        assert "</html>" in html_content

    def test_html_to_pdf_content_conversion(self):
        """Test conversion from HTML to PDF content structure."""
        # Create test report
        report = ReportData(
            title="Conversion Test",
            subtitle="Testing HTML to PDF conversion"
        )

        report.add_section(ReportSection(
            title="Text Section",
            content="Sample text content",
            section_type="text",
            order=1
        ))

        report.add_section(ReportSection(
            title="List Section",
            content=["Item 1", "Item 2", "Item 3"],
            section_type="list",
            order=2
        ))

        # Render HTML first
        html_content = self.pdf_generator.template_engine.render_report(report)

        # Convert to PDF content structure
        pdf_content = self.pdf_generator._convert_html_to_pdf_content(html_content, report)

        assert isinstance(pdf_content, list)
        assert len(pdf_content) > 0

        # Check for title
        title_elements = [item for item in pdf_content if item.get("type") == "title"]
        assert len(title_elements) == 1
        assert title_elements[0]["text"] == "Conversion Test"

        # Check for headings
        subtitle_elements = [item for item in pdf_content if item.get("type") == "subtitle"]
        section_header_elements = [item for item in pdf_content if item.get("type") == "section_header"]
        assert len(subtitle_elements) == 1  # subtitle
        assert len(section_header_elements) >= 2  # section titles

        # Check for bullet list
        list_elements = [item for item in pdf_content if item.get("type") == "bullet_list"]
        assert len(list_elements) == 1
        assert "Item 1" in list_elements[0]["items"]

    def test_confidential_report_generation(self):
        """Test generating a confidential report with proper markings."""
        report = ReportData(
            title="Confidential Test Report",
            metadata={"confidential": True}
        )

        report.add_section(ReportSection(
            title="Sensitive Information",
            content="This report contains confidential information.",
            section_type="text",
            order=1
        ))

        # Generate PDF
        pdf_bytes = self.pdf_generator.generate_report_from_template(
            report_data=report,
            return_bytes=True
        )

        assert pdf_bytes is not None

        # Convert to PDF content to check for confidential notice
        html_content = self.pdf_generator.template_engine.render_report(report)
        pdf_content = self.pdf_generator._convert_html_to_pdf_content(html_content, report)

        # Check for confidential notice
        confidential_elements = [
            item for item in pdf_content
            if item.get("type") == "paragraph" and "CONFIDENTIAL" in item.get("text", "")
        ]
        assert len(confidential_elements) == 1

    def test_table_section_conversion(self):
        """Test conversion of table sections to PDF format."""
        report = ReportData(title="Table Test Report")

        # Test structured table
        report.add_section(ReportSection(
            title="Structured Table",
            content={
                "headers": ["Name", "Value", "Status"],
                "rows": [
                    ["Metric A", "100", "Good"],
                    ["Metric B", "85", "Fair"]
                ]
            },
            section_type="table",
            order=1
        ))

        # Test key-value table
        report.add_section(ReportSection(
            title="Key-Value Table",
            content={
                "Setting A": "Value A",
                "Setting B": "Value B"
            },
            section_type="table",
            order=2
        ))

        # Convert to PDF content
        html_content = self.pdf_generator.template_engine.render_report(report)
        pdf_content = self.pdf_generator._convert_html_to_pdf_content(html_content, report)

        # Check for table elements
        table_elements = [item for item in pdf_content if item.get("type") == "table"]
        assert len(table_elements) == 2

        # Check structured table
        structured_table = table_elements[0]
        assert structured_table["data"][0] == ["Name", "Value", "Status"]  # Headers
        assert structured_table["data"][1] == ["Metric A", "100", "Good"]  # First row

        # Check key-value table
        kv_table = table_elements[1]
        assert kv_table["data"][0] == ["Key", "Value"]  # Headers
        assert ["Setting A", "Value A"] in kv_table["data"]

    def test_chart_section_conversion(self):
        """Test conversion of chart sections to PDF format."""
        report = ReportData(title="Chart Test Report")

        report.add_section(ReportSection(
            title="Performance Chart",
            content={
                "chart_type": "bar",
                "data": [
                    {"label": "Q1", "value": 75},
                    {"label": "Q2", "value": 85},
                    {"label": "Q3", "value": 90}
                ],
                "max_value": 100
            },
            section_type="chart",
            order=1
        ))

        # Convert to PDF content
        html_content = self.pdf_generator.template_engine.render_report(report)
        pdf_content = self.pdf_generator._convert_html_to_pdf_content(html_content, report)

        # Charts should be converted to tables
        table_elements = [item for item in pdf_content if item.get("type") == "table"]
        assert len(table_elements) == 1

        chart_table = table_elements[0]
        assert chart_table["data"][0] == ["Item", "Value"]  # Headers
        assert ["Q1", "75"] in chart_table["data"]
        assert ["Q2", "85"] in chart_table["data"]
        assert ["Q3", "90"] in chart_table["data"]

    def test_multiple_template_types(self):
        """Test that different template files can be used."""
        # The default template should work
        report = ReportData(title="Default Template Test")

        pdf_bytes = self.pdf_generator.generate_report_from_template(
            report_data=report,
            template_name="audit_report.html",
            return_bytes=True
        )

        assert pdf_bytes is not None
        assert isinstance(pdf_bytes, bytes)

    def test_error_handling_invalid_template(self):
        """Test error handling for invalid template names."""
        report = ReportData(title="Error Test Report")

        with pytest.raises(Exception):
            self.pdf_generator.generate_report_from_template(
                report_data=report,
                template_name="non_existent_template.html",
                return_bytes=True
            )

    def test_date_formatting_in_reports(self):
        """Test that dates are properly formatted in reports."""
        test_date = datetime(2023, 12, 25, 15, 30, 0)

        report = ReportData(
            title="Date Test Report",
            report_date=test_date
        )

        # Convert to PDF content
        html_content = self.pdf_generator.template_engine.render_report(report)
        pdf_content = self.pdf_generator._convert_html_to_pdf_content(html_content, report)

        # Check for formatted date
        date_elements = [
            item for item in pdf_content
            if item.get("type") == "paragraph" and "Generated:" in item.get("text", "")
        ]
        assert len(date_elements) == 1
        assert "December 25, 2023" in date_elements[0]["text"]


class TestTemplateEngineStandalone:
    """Test template engine functionality independently."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.engine = ReportTemplateEngine(template_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_sample_report_creation(self):
        """Test creating and rendering sample report."""
        report = self.engine.create_sample_report()

        assert report.title == "Lead Generation Audit Report"
        assert len(report.sections) > 0

        # Render the report
        html_content = self.engine.render_report(report)

        assert "Lead Generation Audit Report" in html_content
        assert "Anthrasite Lead Factory" in html_content
        assert "Executive Summary" in html_content
        assert "Key Performance Metrics" in html_content
        assert "CONFIDENTIAL" in html_content

    def test_available_templates(self):
        """Test getting list of available templates."""
        templates = self.engine.get_available_templates()

        assert "audit_report.html" in templates
        assert "table_section.html" in templates
        assert "chart_section.html" in templates
