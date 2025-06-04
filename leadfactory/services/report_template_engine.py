"""
Report Template Engine for PDF Generation

This module provides a flexible template system for generating audit reports
with dynamic data injection and consistent styling.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """Represents a section in an audit report."""

    title: str
    content: Union[str, List[str], Dict[str, Any]]
    section_type: str = "text"  # text, table, chart, list
    order: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportData:
    """Data model for audit report content."""

    title: str
    subtitle: Optional[str] = None
    company_name: str = ""
    report_date: datetime = field(default_factory=datetime.now)
    sections: List[ReportSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_section(self, section: ReportSection) -> None:
        """Add a section to the report."""
        self.sections.append(section)
        # Sort sections by order
        self.sections.sort(key=lambda x: x.order)

    def get_section(self, title: str) -> Optional[ReportSection]:
        """Get a section by title."""
        for section in self.sections:
            if section.title == title:
                return section
        return None


class ReportTemplateEngine:
    """Template engine for generating audit reports."""

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the template engine.

        Args:
            template_dir: Directory containing template files
        """
        if template_dir is None:
            # Default to templates directory in the same package
            template_dir = os.path.join(os.path.dirname(__file__), "templates")

        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(exist_ok=True)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self._register_filters()

        # Create default templates if they don't exist
        self._create_default_templates()

    def _register_filters(self):
        """Register custom Jinja2 filters."""

        def format_currency(value, currency="$"):
            """Format a number as currency."""
            try:
                if currency == "$":
                    return f"${value:,.2f}"
                else:
                    return f"{value:,.2f} {currency}"
            except (ValueError, TypeError):
                return str(value)

        def format_percentage(value, precision=1):
            """Format a decimal as percentage."""
            try:
                return f"{value * 100:.{precision}f}%"
            except (ValueError, TypeError):
                return str(value)

        def format_date(value, format_str="%B %d, %Y at %I:%M %p"):
            """Format a datetime object."""
            try:
                if hasattr(value, "strftime"):
                    return value.strftime(format_str)
                return str(value)
            except (ValueError, TypeError):
                return str(value)

        def truncate_text(value, length=50):
            """Truncate text to specified length."""
            try:
                text = str(value)
                if len(text) <= length:
                    return text
                return text[:length] + "..."
            except (ValueError, TypeError):
                return str(value)

        # Register filters
        self.env.filters["format_currency"] = format_currency
        self.env.filters["format_percentage"] = format_percentage
        self.env.filters["format_date"] = format_date
        self.env.filters["truncate_text"] = truncate_text

    def _create_default_templates(self):
        """Create default templates if they don't exist."""

        # Main audit report template
        audit_template_path = self.template_dir / "audit_report.html"
        if not audit_template_path.exists():
            audit_template_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_data.title }}</title>
    <style>
        {{ css_content | safe }}
    </style>
</head>
<body>
    <div class="report-container">
        <!-- Header -->
        <header class="report-header">
            <div class="header-content">
                <h1 class="report-title">{{ report_data.title }}</h1>
                {% if report_data.subtitle %}
                <h2 class="report-subtitle">{{ report_data.subtitle }}</h2>
                {% endif %}
                <div class="report-meta">
                    {% if report_data.company_name %}
                    <p class="company-name">{{ report_data.company_name }}</p>
                    {% endif %}
                    <p class="report-date">{{ report_data.report_date | format_date }}</p>
                </div>
            </div>
        </header>

        <!-- Content -->
        <main class="report-content">
            {% for section in report_data.sections %}
            <section class="report-section" data-type="{{ section.section_type }}">
                <h3 class="section-title">{{ section.title }}</h3>
                <div class="section-content">
                    {% if section.section_type == "text" %}
                        {% if section.content is string %}
                            <p>{{ section.content }}</p>
                        {% elif section.content is iterable %}
                            {% for paragraph in section.content %}
                            <p>{{ paragraph }}</p>
                            {% endfor %}
                        {% endif %}
                    {% elif section.section_type == "list" %}
                        <ul class="section-list">
                        {% for item in section.content %}
                            <li>{{ item }}</li>
                        {% endfor %}
                        </ul>
                    {% elif section.section_type == "table" %}
                        {% include "table_section.html" %}
                    {% elif section.section_type == "chart" %}
                        {% include "chart_section.html" %}
                    {% else %}
                        <div class="custom-content">{{ section.content | safe }}</div>
                    {% endif %}
                </div>
            </section>
            {% endfor %}
        </main>

        <!-- Footer -->
        <footer class="report-footer">
            <p>Generated on {{ report_data.report_date | format_date("%Y-%m-%d %H:%M:%S") }}</p>
            {% if report_data.metadata.get("confidential") %}
            <p class="confidential-notice">CONFIDENTIAL - For Internal Use Only</p>
            {% endif %}
        </footer>
    </div>
</body>
</html>"""
            audit_template_path.write_text(audit_template_content)

        # Table section template
        table_template_path = self.template_dir / "table_section.html"
        if not table_template_path.exists():
            table_template_content = """<div class="table-container">
    {% if section.content.headers %}
    <table class="data-table">
        <thead>
            <tr>
                {% for header in section.content.headers %}
                <th>{{ header }}</th>
                {% endfor %}
            </tr>
        </thead>
        <tbody>
            {% for row in section.content.rows %}
            <tr>
                {% for cell in row %}
                <td>{{ cell }}</td>
                {% endfor %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="simple-table">
        {% for key, value in section.content.items() %}
        <div class="table-row">
            <span class="table-key">{{ key }}:</span>
            <span class="table-value">{{ value }}</span>
        </div>
        {% endfor %}
    </div>
    {% endif %}
</div>"""
            table_template_path.write_text(table_template_content)

        # Chart section template
        chart_template_path = self.template_dir / "chart_section.html"
        if not chart_template_path.exists():
            chart_template_content = """<div class="chart-container">
    {% if section.content.chart_type == "bar" %}
        <div class="bar-chart">
            {% for item in section.content.data %}
            <div class="bar-item">
                <div class="bar-label">{{ item.label }}</div>
                <div class="bar-visual">
                    <div class="bar-fill" style="width: {{ (item.value / section.content.max_value * 100) }}%"></div>
                </div>
                <div class="bar-value">{{ item.value }}</div>
            </div>
            {% endfor %}
        </div>
    {% elif section.content.chart_type == "pie" %}
        <div class="pie-chart">
            <!-- Pie chart implementation would go here -->
            <p>Pie chart: {{ section.content.data | length }} items</p>
        </div>
    {% else %}
        <div class="generic-chart">
            <p>Chart Type: {{ section.content.chart_type }}</p>
            <pre>{{ section.content.data | tojson(indent=2) }}</pre>
        </div>
    {% endif %}
</div>"""
            chart_template_path.write_text(chart_template_content)

        # CSS styles
        css_template_path = self.template_dir / "styles.css"
        if not css_template_path.exists():
            css_content = """/* Report Styles */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
    color: #333;
    margin: 0;
    padding: 0;
    background: #fff;
}

.report-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}

/* Header Styles */
.report-header {
    border-bottom: 3px solid #007bff;
    margin-bottom: 30px;
    padding-bottom: 20px;
}

.report-title {
    color: #007bff;
    font-size: 2.5em;
    margin: 0 0 10px 0;
    font-weight: 300;
}

.report-subtitle {
    color: #666;
    font-size: 1.3em;
    margin: 0 0 15px 0;
    font-weight: 400;
}

.report-meta {
    color: #888;
    font-size: 0.9em;
}

.company-name {
    font-weight: 600;
    color: #555;
    margin: 5px 0;
}

.report-date {
    margin: 5px 0;
}

/* Section Styles */
.report-section {
    margin-bottom: 30px;
    page-break-inside: avoid;
}

.section-title {
    color: #007bff;
    font-size: 1.4em;
    margin: 0 0 15px 0;
    padding-bottom: 5px;
    border-bottom: 1px solid #eee;
}

.section-content {
    margin-left: 10px;
}

.section-content p {
    margin: 10px 0;
    text-align: justify;
}

/* List Styles */
.section-list {
    margin: 15px 0;
    padding-left: 20px;
}

.section-list li {
    margin: 8px 0;
}

/* Table Styles */
.table-container {
    margin: 20px 0;
    overflow-x: auto;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.data-table th,
.data-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}

.data-table th {
    background-color: #f8f9fa;
    font-weight: 600;
    color: #555;
}

.data-table tr:hover {
    background-color: #f5f5f5;
}

.simple-table {
    background: #f9f9f9;
    padding: 15px;
    border-radius: 5px;
    border-left: 4px solid #007bff;
}

.table-row {
    display: flex;
    margin: 8px 0;
    align-items: center;
}

.table-key {
    font-weight: 600;
    min-width: 150px;
    color: #555;
}

.table-value {
    color: #333;
}

/* Chart Styles */
.chart-container {
    margin: 20px 0;
    padding: 15px;
    background: #f9f9f9;
    border-radius: 5px;
}

.bar-chart {
    margin: 15px 0;
}

.bar-item {
    display: flex;
    align-items: center;
    margin: 10px 0;
    gap: 10px;
}

.bar-label {
    min-width: 120px;
    font-weight: 500;
    color: #555;
}

.bar-visual {
    flex: 1;
    height: 20px;
    background: #e9ecef;
    border-radius: 10px;
    overflow: hidden;
}

.bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #007bff, #0056b3);
    border-radius: 10px;
    transition: width 0.3s ease;
}

.bar-value {
    min-width: 60px;
    text-align: right;
    font-weight: 600;
    color: #007bff;
}

/* Footer Styles */
.report-footer {
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #eee;
    text-align: center;
    color: #888;
    font-size: 0.9em;
}

.confidential-notice {
    color: #dc3545;
    font-weight: 600;
    margin-top: 10px;
}

/* Print Styles */
@media print {
    body {
        font-size: 12pt;
    }

    .report-container {
        max-width: none;
        margin: 0;
        padding: 0;
    }

    .report-section {
        page-break-inside: avoid;
    }

    .section-title {
        page-break-after: avoid;
    }
}

/* PDF-specific optimizations */
@page {
    margin: 1in;
    size: letter;
}"""
            css_template_path.write_text(css_content)

    def render_report(
        self, report_data: ReportData, template_name: str = "audit_report.html"
    ) -> str:
        """
        Render a report using the specified template.

        Args:
            report_data: The report data to render
            template_name: Name of the template file to use

        Returns:
            Rendered HTML content
        """
        try:
            template = self.env.get_template(template_name)

            # Load CSS content
            css_path = self.template_dir / "styles.css"
            css_content = ""
            if css_path.exists():
                css_content = css_path.read_text()

            # Render the template
            html_content = template.render(
                report_data=report_data, css_content=css_content
            )

            return html_content

        except Exception as e:
            logger.error(f"Error rendering report template: {e}")
            raise

    def create_sample_report(self) -> ReportData:
        """Create a sample report for testing."""
        report = ReportData(
            title="Lead Generation Audit Report",
            subtitle="Comprehensive Analysis and Recommendations",
            company_name="Anthrasite Lead Factory",
            report_date=datetime.now(),
            metadata={"confidential": True},
        )

        # Executive Summary
        report.add_section(
            ReportSection(
                title="Executive Summary",
                content=[
                    "This audit report provides a comprehensive analysis of the current lead generation processes and identifies key areas for improvement.",
                    "Our analysis reveals significant opportunities to optimize conversion rates and reduce customer acquisition costs.",
                    "The following recommendations are prioritized based on potential impact and implementation complexity.",
                ],
                section_type="text",
                order=1,
            )
        )

        # Key Metrics
        metrics_data = {
            "headers": ["Metric", "Current Value", "Target Value", "Status"],
            "rows": [
                ["Conversion Rate", "2.3%", "4.0%", "Below Target"],
                ["Cost Per Lead", "$45.20", "$35.00", "Above Target"],
                ["Lead Quality Score", "7.2/10", "8.5/10", "Improving"],
                ["Monthly Lead Volume", "1,250", "1,500", "On Track"],
            ],
        }

        report.add_section(
            ReportSection(
                title="Key Performance Metrics",
                content=metrics_data,
                section_type="table",
                order=2,
            )
        )

        # Recommendations
        recommendations = [
            "Implement A/B testing for landing page optimization",
            "Enhance lead scoring algorithm with behavioral data",
            "Integrate marketing automation for nurture campaigns",
            "Optimize form fields to reduce abandonment rates",
            "Implement retargeting campaigns for website visitors",
        ]

        report.add_section(
            ReportSection(
                title="Recommendations",
                content=recommendations,
                section_type="list",
                order=3,
            )
        )

        # Performance Chart
        chart_data = {
            "chart_type": "bar",
            "data": [
                {"label": "Email Campaigns", "value": 85},
                {"label": "Social Media", "value": 65},
                {"label": "Paid Search", "value": 92},
                {"label": "Content Marketing", "value": 78},
                {"label": "Referrals", "value": 88},
            ],
            "max_value": 100,
        }

        report.add_section(
            ReportSection(
                title="Channel Performance (%)",
                content=chart_data,
                section_type="chart",
                order=4,
            )
        )

        return report

    def get_available_templates(self) -> List[str]:
        """Get list of available template files."""
        templates = []
        for file_path in self.template_dir.glob("*.html"):
            templates.append(file_path.name)
        return templates


# Helper functions for common formatting needs
def format_financial_data(
    data: Dict[str, float], currency: str = "USD"
) -> Dict[str, str]:
    """Format financial data for display."""
    formatted = {}
    for key, value in data.items():
        if currency == "USD":
            formatted[key] = f"${value:,.2f}"
        else:
            formatted[key] = f"{value:,.2f} {currency}"
    return formatted


def create_comparison_table(
    before: Dict[str, Any],
    after: Dict[str, Any],
    title_before: str = "Before",
    title_after: str = "After",
) -> Dict[str, Any]:
    """Create a comparison table structure."""
    headers = ["Metric", title_before, title_after, "Change"]
    rows = []

    for key in before:
        if key in after:
            before_val = before[key]
            after_val = after[key]

            # Calculate change
            if isinstance(before_val, (int, float)) and isinstance(
                after_val, (int, float)
            ):
                if before_val != 0:
                    change_pct = ((after_val - before_val) / before_val) * 100
                    change_str = f"{change_pct:+.1f}%"
                else:
                    change_str = "N/A"
            else:
                change_str = "Changed" if before_val != after_val else "No Change"

            rows.append([key, str(before_val), str(after_val), change_str])

    return {"headers": headers, "rows": rows}


def generate_executive_summary(
    metrics: Dict[str, Any], recommendations: List[str]
) -> List[str]:
    """Generate an executive summary based on metrics and recommendations."""
    summary = [
        f"This report analyzes {len(metrics)} key performance indicators and provides {len(recommendations)} actionable recommendations.",
        "The analysis identifies both strengths and areas for improvement in current operations.",
        "Implementation of the recommended changes is expected to drive significant performance improvements.",
    ]

    # Add metric-specific insights
    if "conversion_rate" in metrics:
        rate = metrics["conversion_rate"]
        if rate < 3.0:
            summary.append(
                f"Current conversion rate of {rate}% indicates significant optimization opportunities."
            )
        elif rate > 5.0:
            summary.append(
                f"Strong conversion rate of {rate}% demonstrates effective lead generation processes."
            )

    return summary
