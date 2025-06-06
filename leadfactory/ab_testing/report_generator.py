"""
A/B Test Report Generator - PDF report generation with statistical analysis.

Implements AB-3: Test End Auto-report functionality.
- Generates comprehensive PDF reports for completed A/B tests
- Includes statistical significance testing
- Provides actionable insights and recommendations
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from leadfactory.ab_testing.ab_test_manager import ABTestManager
from leadfactory.ab_testing.statistical_engine import StatisticalEngine
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ABTestReportGenerator:
    """Service for generating comprehensive A/B test reports."""

    def __init__(self):
        """Initialize the report generator."""
        self.ab_manager = ABTestManager()
        self.stats_engine = StatisticalEngine()

        if REPORTLAB_AVAILABLE:
            self.styles = getSampleStyleSheet()

            # Custom styles
            self.styles.add(
                ParagraphStyle(
                    name="CustomHeading",
                    parent=self.styles["Heading1"],
                    fontSize=16,
                    spaceAfter=12,
                    textColor=colors.HexColor("#2c3e50"),
                )
            )

            self.styles.add(
                ParagraphStyle(
                    name="Insight",
                    parent=self.styles["Normal"],
                    fontSize=11,
                    spaceAfter=8,
                    leftIndent=20,
                    textColor=colors.HexColor("#34495e"),
                    backColor=colors.HexColor("#ecf0f1"),
                )
            )
        else:
            self.styles = None

    def generate_test_end_report(
        self,
        test_id: str,
        auto_email: bool = True,
        recipient_emails: Optional[List[str]] = None,
    ) -> bytes:
        """Generate comprehensive report for a completed A/B test.

        Args:
            test_id: Test identifier
            auto_email: Whether to automatically email the report
            recipient_emails: List of email addresses to send report to

        Returns:
            PDF report as bytes
        """
        try:
            # Get test results
            test_results = self.ab_manager.get_test_results(test_id)

            # Run statistical analysis
            stats_results = self.stats_engine.analyze_test_results(test_results)

            if not REPORTLAB_AVAILABLE:
                # Generate simple text report as fallback
                return self._generate_text_report(test_results, stats_results)

            # Generate PDF
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=letter,
                rightMargin=0.75 * inch,
                leftMargin=0.75 * inch,
                topMargin=1 * inch,
                bottomMargin=1 * inch,
            )

            # Build report content
            story = []
            self._add_title_section(story, test_results)
            self._add_executive_summary(story, test_results, stats_results)
            self._add_test_configuration(story, test_results)
            self._add_statistical_analysis(story, stats_results)
            self._add_variant_comparison(story, test_results, stats_results)
            self._add_insights_and_recommendations(story, test_results, stats_results)
            self._add_technical_details(story, stats_results)

            # Build PDF
            doc.build(story)
            pdf_bytes = pdf_buffer.getvalue()
            pdf_buffer.close()

            logger.info(f"Generated A/B test report for test {test_id}")

            # Auto-email if requested
            if auto_email and recipient_emails:
                self._send_report_email(
                    test_id, pdf_bytes, recipient_emails, stats_results
                )

            return pdf_bytes

        except Exception as e:
            logger.error(f"Error generating A/B test report: {e}")
            raise

    def _add_title_section(self, story: List, test_results: Dict[str, Any]):
        """Add title section to report."""
        test_config = test_results["test_config"]

        # Title
        title = Paragraph(f"A/B Test Report: {test_config.name}", self.styles["Title"])
        story.append(title)
        story.append(Spacer(1, 0.2 * inch))

        # Metadata table
        metadata_data = [
            ["Test ID", test_config.id],
            ["Test Type", test_config.test_type.value.replace("_", " ").title()],
            ["Status", test_config.status.value.title()],
            [
                "Duration",
                self._format_duration(test_config.start_date, test_config.end_date),
            ],
            ["Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
        ]

        metadata_table = Table(metadata_data, colWidths=[2 * inch, 3 * inch])
        metadata_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#dee2e6")),
                ]
            )
        )

        story.append(metadata_table)
        story.append(Spacer(1, 0.3 * inch))

    def _add_executive_summary(
        self, story: List, test_results: Dict[str, Any], stats_results: Dict[str, Any]
    ):
        """Add executive summary section."""
        story.append(Paragraph("Executive Summary", self.styles["CustomHeading"]))

        # Key findings
        winner = stats_results.get("recommended_variant")
        p_value = stats_results.get("p_value", 1.0)
        confidence_level = (1 - stats_results.get("significance_threshold", 0.05)) * 100

        if p_value < stats_results.get("significance_threshold", 0.05):
            significance_text = f"statistically significant (p < {stats_results.get('significance_threshold', 0.05)})"
            recommendation = f"✅ **Recommend implementing {winner}** - Results are {significance_text}"
        else:
            recommendation = f"⚠️ **No clear winner** - Results are not statistically significant (p = {p_value:.4f})"

        summary_text = f"""
        <b>Test Outcome:</b> {recommendation}<br/>
        <b>Confidence Level:</b> {confidence_level}%<br/>
        <b>Total Participants:</b> {test_results.get('total_assignments', 0):,}<br/>
        <b>Test Duration:</b> {self._format_duration(
            test_results['test_config'].start_date,
            test_results['test_config'].end_date
        )}
        """

        story.append(Paragraph(summary_text, self.styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))

    def _add_test_configuration(self, story: List, test_results: Dict[str, Any]):
        """Add test configuration section."""
        story.append(Paragraph("Test Configuration", self.styles["CustomHeading"]))

        test_config = test_results["test_config"]

        # Configuration details
        config_data = [
            ["Parameter", "Value"],
            ["Target Sample Size", f"{test_config.target_sample_size:,}"],
            ["Significance Threshold", f"{test_config.significance_threshold}"],
            ["Minimum Effect Size", f"{test_config.minimum_effect_size}"],
            ["Number of Variants", f"{len(test_config.variants)}"],
        ]

        config_table = Table(config_data, colWidths=[2.5 * inch, 2.5 * inch])
        config_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        story.append(config_table)
        story.append(Spacer(1, 0.2 * inch))

        # Variants description
        story.append(Paragraph("Test Variants", self.styles["Heading2"]))

        for i, variant in enumerate(test_config.variants):
            variant_name = variant.get("name", f"Variant {i+1}")
            variant_desc = variant.get("description", "No description provided")
            weight = variant.get("weight", 1.0 / len(test_config.variants))

            variant_text = (
                f"<b>{variant_name}</b> (Weight: {weight:.1%})<br/>{variant_desc}"
            )
            story.append(Paragraph(variant_text, self.styles["Normal"]))

        story.append(Spacer(1, 0.2 * inch))

    def _add_statistical_analysis(self, story: List, stats_results: Dict[str, Any]):
        """Add statistical analysis section."""
        story.append(Paragraph("Statistical Analysis", self.styles["CustomHeading"]))

        # Statistical test results
        p_value = stats_results.get("p_value", 1.0)
        effect_size = stats_results.get("effect_size", 0.0)
        power = stats_results.get("statistical_power", 0.0)

        stats_data = [
            ["Metric", "Value", "Interpretation"],
            [
                "P-value",
                f"{p_value:.4f}",
                self._interpret_p_value(
                    p_value, stats_results.get("significance_threshold", 0.05)
                ),
            ],
            [
                "Effect Size",
                f"{effect_size:.4f}",
                self._interpret_effect_size(effect_size),
            ],
            ["Statistical Power", f"{power:.1%}", self._interpret_power(power)],
        ]

        stats_table = Table(stats_data, colWidths=[1.5 * inch, 1.5 * inch, 2.5 * inch])
        stats_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )

        story.append(stats_table)
        story.append(Spacer(1, 0.2 * inch))

    def _add_variant_comparison(
        self, story: List, test_results: Dict[str, Any], stats_results: Dict[str, Any]
    ):
        """Add variant comparison section."""
        story.append(
            Paragraph("Variant Performance Comparison", self.styles["CustomHeading"])
        )

        variant_results = test_results["variant_results"]

        # Build comparison table
        headers = [
            "Variant",
            "Participants",
            "Conversions",
            "Conversion Rate",
            "Confidence Interval",
        ]
        comparison_data = [headers]

        for variant_id, results in variant_results.items():
            variant_name = self._get_variant_name(
                variant_id, test_results["test_config"]
            )
            participants = results["assignments"]

            # Get primary conversion metric (first one found)
            conversion_rates = results.get("conversion_rates", {})
            if conversion_rates:
                primary_metric = list(conversion_rates.keys())[0]
                conv_data = conversion_rates[primary_metric]
                conversions = conv_data["count"]
                conv_rate = conv_data["rate"]

                # Get confidence interval from stats
                ci = stats_results.get("confidence_intervals", {}).get(
                    variant_id, (0, 0)
                )
                ci_text = f"{ci[0]:.1%} - {ci[1]:.1%}"
            else:
                conversions = 0
                conv_rate = 0.0
                ci_text = "N/A"

            comparison_data.append(
                [
                    variant_name,
                    f"{participants:,}",
                    f"{conversions:,}",
                    f"{conv_rate:.2%}",
                    ci_text,
                ]
            )

        comparison_table = Table(
            comparison_data,
            colWidths=[1.2 * inch, 1 * inch, 1 * inch, 1.2 * inch, 1.1 * inch],
        )
        comparison_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27ae60")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        story.append(comparison_table)
        story.append(Spacer(1, 0.2 * inch))

    def _add_insights_and_recommendations(
        self, story: List, test_results: Dict[str, Any], stats_results: Dict[str, Any]
    ):
        """Add insights and recommendations section."""
        story.append(
            Paragraph("Key Insights & Recommendations", self.styles["CustomHeading"])
        )

        insights = self._generate_insights(test_results, stats_results)

        for insight in insights:
            story.append(Paragraph(insight, self.styles["Insight"]))

        story.append(Spacer(1, 0.2 * inch))

    def _add_technical_details(self, story: List, stats_results: Dict[str, Any]):
        """Add technical details section."""
        story.append(Paragraph("Technical Details", self.styles["CustomHeading"]))

        # Statistical methodology
        method_text = f"""
        <b>Statistical Test:</b> {stats_results.get('test_method', 'Chi-square test')}<br/>
        <b>Multiple Comparisons:</b> {stats_results.get('correction_method', 'Bonferroni correction')}<br/>
        <b>Sample Size Calculation:</b> Based on minimum detectable effect size and desired power<br/>
        <b>Confidence Intervals:</b> Calculated using normal approximation with continuity correction
        """

        story.append(Paragraph(method_text, self.styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))

    def _format_duration(
        self, start_date: datetime, end_date: Optional[datetime]
    ) -> str:
        """Format test duration."""
        if not end_date:
            end_date = datetime.utcnow()

        duration = end_date - start_date
        days = duration.days
        hours = duration.seconds // 3600

        if days > 0:
            return f"{days} days, {hours} hours"
        else:
            return f"{hours} hours"

    def _interpret_p_value(self, p_value: float, threshold: float) -> str:
        """Interpret p-value result."""
        if p_value < threshold:
            return f"Significant (< {threshold})"
        elif p_value < threshold * 2:
            return "Marginally significant"
        else:
            return "Not significant"

    def _interpret_effect_size(self, effect_size: float) -> str:
        """Interpret effect size magnitude."""
        if abs(effect_size) < 0.2:
            return "Small effect"
        elif abs(effect_size) < 0.5:
            return "Medium effect"
        else:
            return "Large effect"

    def _interpret_power(self, power: float) -> str:
        """Interpret statistical power."""
        if power >= 0.8:
            return "Adequate power"
        elif power >= 0.6:
            return "Moderate power"
        else:
            return "Low power"

    def _get_variant_name(self, variant_id: str, test_config) -> str:
        """Get variant name from configuration."""
        try:
            variant_idx = int(variant_id.split("_")[1])
            return test_config.variants[variant_idx].get(
                "name", f"Variant {variant_idx + 1}"
            )
        except (IndexError, ValueError):
            return variant_id

    def _generate_insights(
        self, test_results: Dict[str, Any], stats_results: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable insights from test results."""
        insights = []

        # Statistical significance insight
        p_value = stats_results.get("p_value", 1.0)
        threshold = stats_results.get("significance_threshold", 0.05)

        if p_value < threshold:
            winner = stats_results.get("recommended_variant", "Unknown")
            insights.append(
                f"🎯 <b>Clear Winner:</b> {winner} shows statistically significant improvement over other variants."
            )
        else:
            insights.append(
                "📊 <b>Inconclusive Results:</b> No variant shows statistically significant advantage. Consider running longer or with larger sample size."
            )

        # Sample size insight
        total_participants = test_results.get("total_assignments", 0)
        target_size = test_results["test_config"].target_sample_size

        if total_participants < target_size * 0.8:
            insights.append(
                f"⚠️ <b>Sample Size:</b> Test ended with {total_participants:,} participants, below target of {target_size:,}. Results may lack sufficient power."
            )

        # Effect size insight
        effect_size = stats_results.get("effect_size", 0.0)
        if abs(effect_size) > 0.5:
            insights.append(
                "📈 <b>Strong Effect:</b> The observed difference between variants is substantial and likely to have meaningful business impact."
            )
        elif abs(effect_size) < 0.1:
            insights.append(
                "📉 <b>Minimal Effect:</b> The difference between variants is small. Consider if the implementation effort is worthwhile."
            )

        # Business impact insight
        variant_results = test_results["variant_results"]
        if len(variant_results) >= 2:
            rates = []
            for results in variant_results.values():
                conversion_rates = results.get("conversion_rates", {})
                if conversion_rates:
                    primary_rate = list(conversion_rates.values())[0]["rate"]
                    rates.append(primary_rate)

            if rates and max(rates) > 0:
                improvement = (
                    (max(rates) - min(rates)) / min(rates) if min(rates) > 0 else 0
                )
                if improvement > 0.1:
                    insights.append(
                        f"💰 <b>Business Impact:</b> Best performing variant shows {improvement:.1%} improvement, potentially significant for conversion optimization."
                    )

        return insights

    def _generate_text_report(
        self, test_results: Dict[str, Any], stats_results: Dict[str, Any]
    ) -> bytes:
        """Generate simple text report as fallback when PDF libraries unavailable."""
        test_config = test_results["test_config"]

        # Build text report
        report_lines = [
            "=" * 60,
            f"A/B TEST REPORT: {test_config.name}",
            "=" * 60,
            "",
            f"Test ID: {test_config.id}",
            f"Test Type: {test_config.test_type.value.replace('_', ' ').title()}",
            f"Status: {test_config.status.value.title()}",
            f"Duration: {self._format_duration(test_config.start_date, test_config.end_date)}",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 20,
        ]

        # Key findings
        winner = stats_results.get("recommended_variant")
        p_value = stats_results.get("p_value", 1.0)
        confidence_level = (1 - stats_results.get("significance_threshold", 0.05)) * 100

        if p_value < stats_results.get("significance_threshold", 0.05):
            recommendation = f"✅ RECOMMEND IMPLEMENTING {winner} - Results are statistically significant"
        else:
            recommendation = f"⚠️ NO CLEAR WINNER - Results are not statistically significant (p = {p_value:.4f})"

        report_lines.extend(
            [
                f"Test Outcome: {recommendation}",
                f"Confidence Level: {confidence_level}%",
                f"Total Participants: {test_results.get('total_assignments', 0):,}",
                "",
                "VARIANT PERFORMANCE",
                "-" * 20,
            ]
        )

        # Variant comparison
        variant_results = test_results["variant_results"]
        for variant_id, results in variant_results.items():
            variant_name = self._get_variant_name(variant_id, test_config)
            participants = results["assignments"]

            conversion_rates = results.get("conversion_rates", {})
            if conversion_rates:
                primary_metric = list(conversion_rates.keys())[0]
                conv_data = conversion_rates[primary_metric]
                conversions = conv_data["count"]
                conv_rate = conv_data["rate"]

                ci = stats_results.get("confidence_intervals", {}).get(
                    variant_id, (0, 0)
                )
                ci_text = f"{ci[0]:.1%} - {ci[1]:.1%}"
            else:
                conversions = 0
                conv_rate = 0.0
                ci_text = "N/A"

            report_lines.extend(
                [
                    f"{variant_name}:",
                    f"  - Participants: {participants:,}",
                    f"  - Conversions: {conversions:,}",
                    f"  - Conversion Rate: {conv_rate:.2%}",
                    f"  - Confidence Interval: {ci_text}",
                    "",
                ]
            )

        # Statistical analysis
        report_lines.extend(
            [
                "STATISTICAL ANALYSIS",
                "-" * 20,
                f"P-value: {p_value:.4f} ({self._interpret_p_value(p_value, stats_results.get('significance_threshold', 0.05))})",
                f"Effect Size: {stats_results.get('effect_size', 0.0):.4f} ({self._interpret_effect_size(stats_results.get('effect_size', 0.0))})",
                f"Statistical Power: {stats_results.get('statistical_power', 0.0):.1%} ({self._interpret_power(stats_results.get('statistical_power', 0.0))})",
                "",
                "KEY INSIGHTS",
                "-" * 20,
            ]
        )

        # Add insights
        insights = self._generate_insights(test_results, stats_results)
        for insight in insights:
            # Remove HTML tags for text format
            clean_insight = (
                insight.replace("<b>", "").replace("</b>", "").replace("<br/>", "\n")
            )
            report_lines.append(f"• {clean_insight}")

        report_lines.extend(
            ["", "=" * 60, "Generated by LeadFactory A/B Testing Framework", "=" * 60]
        )

        return "\n".join(report_lines).encode("utf-8")

    def _send_report_email(
        self,
        test_id: str,
        pdf_bytes: bytes,
        recipient_emails: List[str],
        stats_results: Dict[str, Any],
    ):
        """Send report via email."""
        try:
            # Determine subject based on results
            p_value = stats_results.get("p_value", 1.0)
            threshold = stats_results.get("significance_threshold", 0.05)

            if p_value < threshold:
                subject = (
                    f"🎯 A/B Test Results: Significant Results - Test {test_id[:8]}"
                )
            else:
                subject = f"📊 A/B Test Results: Inconclusive - Test {test_id[:8]}"

            # Email body
            body = f"""
            Your A/B test has completed and the comprehensive report is attached.

            Test ID: {test_id}
            P-value: {p_value:.4f}
            Status: {'Significant' if p_value < threshold else 'Not significant'}

            Please review the attached PDF for detailed analysis and recommendations.

            Best regards,
            LeadFactory A/B Testing Team
            """

            # Send email with attachment
            for email in recipient_emails:
                self._send_report_email_simple(email, subject, body, pdf_bytes, test_id)

            logger.info(
                f"Sent A/B test report for {test_id} to {len(recipient_emails)} recipients"
            )

        except Exception as e:
            logger.error(f"Failed to send A/B test report email: {e}")

    def _send_report_email_simple(
        self, email: str, subject: str, body: str, pdf_bytes: bytes, test_id: str
    ):
        """Send report email with attachment (mock implementation for testing)."""
        try:
            # In a real implementation, this would use the email service
            # For now, just log the email attempt
            logger.info(f"Would send A/B test report to {email}: {subject}")
            logger.debug(f"Report size: {len(pdf_bytes)} bytes")
            logger.debug(f"Email body preview: {body[:100]}...")
        except Exception as e:
            logger.error(f"Error sending report email to {email}: {e}")


# Global instance
report_generator = ABTestReportGenerator()
