"""
PDF Generation Service for Anthrasite LeadFactory.

This module provides comprehensive PDF generation capabilities including:
- Document creation with custom styling
- Table and chart generation
- Image embedding
- Security features (encryption, watermarking)
- Template-based report generation
"""

import io
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pypdf import PdfReader, PdfWriter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from leadfactory.services.report_template_engine import ReportTemplateEngine

logger = logging.getLogger(__name__)


class WatermarkType(Enum):
    """Types of watermarks that can be applied to PDFs."""

    TEXT = "text"
    IMAGE = "image"
    DIAGONAL_TEXT = "diagonal_text"


class PDFPermissions(Enum):
    """PDF permission levels for access control."""

    PRINT_ALLOWED = "print"
    COPY_ALLOWED = "copy"
    MODIFY_ALLOWED = "modify"
    EXTRACT_ALLOWED = "extract"


@dataclass
class WatermarkConfig:
    """Configuration for PDF watermarks."""

    watermark_type: WatermarkType = WatermarkType.TEXT
    text: Optional[str] = None
    image_path: Optional[str] = None
    opacity: float = 0.3
    font_size: int = 50
    color: str = "grey"
    rotation: int = 45
    position_x: int = 300
    position_y: int = 300


@dataclass
class SecurityConfig:
    """Configuration for PDF security features."""

    enable_encryption: bool = False
    user_password: Optional[str] = None
    owner_password: Optional[str] = None
    permissions: List[PDFPermissions] = None
    watermark: Optional[WatermarkConfig] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []


class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors."""

    pass


@dataclass
class PDFConfiguration:
    """Configuration class for PDF generation settings."""

    def __init__(
        self,
        page_size: tuple = letter,
        margins: Dict[str, float] = None,
        orientation: str = "portrait",
        compression: bool = True,
        security_config: Optional[SecurityConfig] = None,
        # Backward compatibility parameters
        encryption: bool = False,
        password: Optional[str] = None,
        watermark: Optional[str] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        subject: Optional[str] = None,
        creator: str = "Anthrasite LeadFactory",
    ):
        """
        Initialize PDF configuration.

        Args:
            page_size: Page size tuple (default: letter)
            margins: Dict with 'top', 'bottom', 'left', 'right' margins in inches
            orientation: 'portrait' or 'landscape'
            compression: Enable PDF compression
            security_config: Security configuration (new format)
            encryption: Enable PDF encryption (legacy)
            password: Password for encrypted PDFs (legacy)
            watermark: Watermark text (legacy)
            title: Document title
            author: Document author
            subject: Document subject
            creator: Document creator
        """
        self.page_size = page_size
        self.margins = margins or {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0}
        self.orientation = orientation
        self.compression = compression
        self.title = title
        self.author = author
        self.subject = subject
        self.creator = creator

        # Handle backward compatibility
        self.encryption = encryption
        self.password = password
        self.watermark = watermark

        # If security_config is not provided but legacy parameters are used, create one
        if security_config is None and (encryption or password or watermark):
            watermark_config = None
            if watermark:
                watermark_config = WatermarkConfig(text=watermark)

            self.security_config = SecurityConfig(
                enable_encryption=encryption,
                user_password=password,
                watermark=watermark_config,
            )
        else:
            self.security_config = security_config

        # Validate configuration
        self._validate_config()

    def _validate_config(self):
        """Validate configuration parameters."""
        if self.page_size not in [letter, A4]:
            raise PDFGenerationError(f"Unsupported page size: {self.page_size}")

        if self.orientation not in ["portrait", "landscape"]:
            raise PDFGenerationError(f"Invalid orientation: {self.orientation}")

        # Check both legacy and new encryption settings
        if self.encryption and not self.password:
            raise PDFGenerationError("Password required for encrypted PDFs")

        if self.security_config and self.security_config.enable_encryption:
            if not self.security_config.user_password:
                raise PDFGenerationError("Password required for encrypted PDFs")

        for margin_key in ["top", "bottom", "left", "right"]:
            if margin_key not in self.margins:
                raise PDFGenerationError(f"Missing margin: {margin_key}")
            if not isinstance(self.margins[margin_key], (int, float)):
                raise PDFGenerationError(f"Invalid margin value: {margin_key}")


class PDFGenerator:
    """Main PDF generation service using ReportLab.

    This service provides a high-level interface for generating PDFs
    with support for templates, styling, and security features.
    """

    def __init__(
        self,
        config: Optional[PDFConfiguration] = None,
        template_dir: Optional[str] = None,
    ):
        """
        Initialize PDF generator.

        Args:
            config: PDF configuration object
            template_dir: Directory containing report templates
        """
        self.config = config or PDFConfiguration()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self._register_fonts()

        # Initialize template engine
        self.template_engine = ReportTemplateEngine(template_dir)

        logger.info("PDF Generator initialized with ReportLab")

    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the PDF."""
        # Custom title style
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Title"],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER,
            )
        )

        # Custom subtitle style
        self.styles.add(
            ParagraphStyle(
                name="CustomSubtitle",
                parent=self.styles["Heading1"],
                fontSize=18,
                spaceAfter=20,
                alignment=TA_CENTER,
            )
        )

        # Section header style
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=16,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.darkblue,
            )
        )

        # Custom body text style
        self.styles.add(
            ParagraphStyle(
                name="CustomBodyText",
                parent=self.styles["Normal"],
                fontSize=10,
                spaceAfter=6,
                alignment=TA_LEFT,
            )
        )

        # Highlight style for important information
        self.styles.add(
            ParagraphStyle(
                name="Highlight",
                parent=self.styles["Normal"],
                fontSize=12,
                textColor=colors.red,
                backColor=colors.yellow,
            )
        )

        # Warning style for confidential reports
        self.styles.add(
            ParagraphStyle(
                name="warning",
                parent=self.styles["Normal"],
                fontSize=12,
                textColor=colors.red,
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            )
        )

    def _register_fonts(self):
        """Register custom fonts if available."""
        # This is a placeholder for custom font registration
        # In a production environment, you might want to register
        # corporate fonts or other custom typefaces
        pass

    def generate_document(
        self,
        content: List[Dict[str, Any]],
        output_path: Optional[str] = None,
        return_bytes: bool = False,
    ) -> Union[str, bytes, None]:
        """
        Generate a PDF document from structured content.

        Args:
            content: List of content elements (paragraphs, tables, images, etc.)
            output_path: Path to save the PDF file
            return_bytes: Return PDF as bytes instead of saving to file

        Returns:
            Path to generated file, bytes content, or None
        """
        try:
            # Create output buffer or file
            if return_bytes:
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(
                    buffer,
                    pagesize=self.config.page_size,
                    topMargin=self.config.margins["top"] * inch,
                    bottomMargin=self.config.margins["bottom"] * inch,
                    leftMargin=self.config.margins["left"] * inch,
                    rightMargin=self.config.margins["right"] * inch,
                    title=self.config.title,
                    author=self.config.author,
                    subject=self.config.subject,
                    creator=self.config.creator,
                )
            else:
                if not output_path:
                    raise PDFGenerationError(
                        "Output path required when not returning bytes"
                    )

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                doc = SimpleDocTemplate(
                    output_path,
                    pagesize=self.config.page_size,
                    topMargin=self.config.margins["top"] * inch,
                    bottomMargin=self.config.margins["bottom"] * inch,
                    leftMargin=self.config.margins["left"] * inch,
                    rightMargin=self.config.margins["right"] * inch,
                    title=self.config.title,
                    author=self.config.author,
                    subject=self.config.subject,
                    creator=self.config.creator,
                )

            # Build story from content
            story = self._build_story(content)

            # Build PDF
            doc.build(
                story, onFirstPage=self._add_watermark, onLaterPages=self._add_watermark
            )

            if return_bytes:
                buffer.seek(0)
                pdf_bytes = buffer.getvalue()
                buffer.close()

                # Apply encryption if configured
                if (
                    self.config.security_config
                    and self.config.security_config.enable_encryption
                ) or self.config.encryption:
                    pdf_bytes = self._encrypt_pdf(pdf_bytes)

                logger.info("PDF generated successfully as bytes")
                return pdf_bytes
            else:
                # Apply encryption if configured
                if (
                    self.config.security_config
                    and self.config.security_config.enable_encryption
                ) or self.config.encryption:
                    self._encrypt_pdf_file(output_path)

                logger.info(f"PDF generated successfully: {output_path}")
                return output_path

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise PDFGenerationError(f"Failed to generate PDF: {e}")

    def _build_story(self, content: List[Dict[str, Any]]) -> List:
        """
        Build a ReportLab story from structured content.

        Args:
            content: List of content elements

        Returns:
            List of ReportLab flowables
        """
        story = []

        for element in content:
            element_type = element.get("type", "").lower()

            if element_type == "title":
                story.append(Paragraph(element["text"], self.styles["CustomTitle"]))
                story.append(Spacer(1, 20))

            elif element_type == "subtitle":
                story.append(Paragraph(element["text"], self.styles["CustomSubtitle"]))
                story.append(Spacer(1, 15))

            elif element_type == "heading":
                level = element.get("level", 1)
                if level == 1:
                    style = self.styles["Heading1"]
                elif level == 2:
                    style = self.styles["SectionHeader"]
                else:
                    style = self.styles["Heading3"]
                story.append(Paragraph(element["text"], style))
                story.append(Spacer(1, 10))

            elif element_type == "paragraph":
                style_name = element.get("style", "CustomBodyText")
                if style_name in self.styles:
                    style = self.styles[style_name]
                else:
                    style = self.styles["Normal"]
                story.append(Paragraph(element["text"], style))

            elif element_type == "bullet_list":
                for item in element.get("items", []):
                    bullet_text = f"• {item}"
                    story.append(Paragraph(bullet_text, self.styles["Normal"]))
                story.append(Spacer(1, 10))

            elif element_type == "table":
                table = self._create_table(element)
                if table:
                    story.append(table)
                    story.append(Spacer(1, 15))

            elif element_type == "image":
                image = self._create_image(element)
                if image:
                    story.append(image)
                    story.append(Spacer(1, 15))

            elif element_type == "spacer":
                height = element.get("height", 20)
                story.append(Spacer(1, height))

            elif element_type == "page_break":
                story.append(PageBreak())

            elif element_type == "section_header":
                story.append(Paragraph(element["text"], self.styles["SectionHeader"]))
                story.append(Spacer(1, 10))

        return story

    def _create_table(self, element: Dict[str, Any]) -> Optional[Table]:
        """Create a formatted table from element data."""
        data = element.get("data", [])
        if not data:
            return Spacer(1, 12)  # Return spacer for empty data

        # Create table
        table = Table(data)

        # Apply default styling
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 14),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]

        # Apply custom styling if provided
        custom_style = element.get("style", [])
        if isinstance(custom_style, str):
            # If style is a string name, ignore it for now (use default styling)
            pass
        elif isinstance(custom_style, list):
            table_style.extend(custom_style)

        table.setStyle(TableStyle(table_style))

        return table

    def _create_image(self, element: Dict[str, Any]) -> Optional[Image]:
        """Create an image from element data."""
        image_path = element.get("path")
        image_data = element.get("data")

        if not image_path and not image_data:
            return None

        try:
            if image_path and os.path.exists(image_path):
                width = element.get("width", 400)
                height = element.get("height", 300)
                return Image(image_path, width=width, height=height)
            elif image_data:
                # Handle base64 or binary image data
                # This would require additional processing
                pass
        except Exception as e:
            logger.warning(f"Failed to create image: {e}")

        return None

    def _add_watermark(self, canvas_obj, doc):
        """Add watermark to PDF pages."""
        if (
            self.config.security_config and self.config.security_config.watermark
        ) or self.config.watermark:
            if self.config.security_config and self.config.security_config.watermark:
                watermark_config = self.config.security_config.watermark
            else:
                watermark_config = WatermarkConfig(text=self.config.watermark)
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", watermark_config.font_size)
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.setFillAlpha(watermark_config.opacity)
            canvas_obj.rotate(watermark_config.rotation)
            canvas_obj.drawCentredText(
                watermark_config.position_x,
                watermark_config.position_y,
                watermark_config.text,
            )
            canvas_obj.restoreState()

    def _encrypt_pdf(self, pdf_bytes: bytes) -> bytes:
        """Encrypt PDF bytes using PyPDF2."""
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        pdf_writer = PdfWriter()

        for page_num in range(len(pdf_reader.pages)):
            pdf_writer.addPage(pdf_reader.pages[page_num])

        if (
            self.config.security_config
            and self.config.security_config.enable_encryption
        ) or self.config.encryption:
            if (
                self.config.security_config
                and self.config.security_config.user_password
            ):
                pdf_writer.encrypt(
                    user_pwd=self.config.security_config.user_password,
                    owner_pwd=self.config.security_config.owner_password,
                    use_128bit=True,
                )
            elif self.config.password:
                pdf_writer.encrypt(user_pwd=self.config.password, use_128bit=True)

        encrypted_pdf_bytes = io.BytesIO()
        pdf_writer.write(encrypted_pdf_bytes)
        encrypted_pdf_bytes.seek(0)

        return encrypted_pdf_bytes.getvalue()

    def _encrypt_pdf_file(self, file_path: str):
        """Encrypt PDF file using PyPDF2."""
        pdf_reader = PdfReader(file_path)
        pdf_writer = PdfWriter()

        for page_num in range(len(pdf_reader.pages)):
            pdf_writer.addPage(pdf_reader.pages[page_num])

        if (
            self.config.security_config
            and self.config.security_config.enable_encryption
        ) or self.config.encryption:
            if (
                self.config.security_config
                and self.config.security_config.user_password
            ):
                pdf_writer.encrypt(
                    user_pwd=self.config.security_config.user_password,
                    owner_pwd=self.config.security_config.owner_password,
                    use_128bit=True,
                )
            elif self.config.password:
                pdf_writer.encrypt(user_pwd=self.config.password, use_128bit=True)

        with open(file_path, "wb") as encrypted_file:
            pdf_writer.write(encrypted_file)

    def generate_audit_report(
        self,
        business_data: Dict[str, Any],
        audit_results: Dict[str, Any],
        output_path: Optional[str] = None,
        return_bytes: bool = False,
    ) -> Union[str, bytes, None]:
        """
        Generate a comprehensive audit report PDF.

        Args:
            business_data: Dictionary containing business information
            audit_results: Dictionary containing audit findings and recommendations
            output_path: Optional output file path
            return_bytes: Return PDF as bytes instead of saving to file

        Returns:
            Path to generated file, bytes content, or None
        """
        try:
            # Update config with audit report metadata
            business_name = business_data.get("name", "Unknown Business")
            self.config.title = f"Audit Report - {business_name}"
            self.config.subject = "Business Audit Analysis"

            # Build audit report content
            content = self._build_audit_report_content(business_data, audit_results)

            # Generate the PDF
            return self.generate_document(content, output_path, return_bytes)

        except Exception as e:
            logger.error(f"Failed to generate audit report: {str(e)}")
            raise PDFGenerationError(f"Failed to generate audit report: {str(e)}")

    def _build_audit_report_content(
        self, business_data: Dict[str, Any], audit_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build content structure for audit report."""
        content = []

        # Title
        content.append({"type": "title", "text": "Business Audit Report"})

        # Executive Summary section
        content.append({"type": "section_header", "text": "Executive Summary"})

        if "summary" in audit_results:
            content.append({"type": "paragraph", "text": audit_results["summary"]})

        content.append({"type": "spacer", "height": 20})

        # Business information section
        content.append({"type": "section_header", "text": "Business Information"})

        # Business info table
        business_table = self._build_business_info_table(business_data)
        content.append({"type": "table", "data": business_table, "style": "default"})

        content.append({"type": "spacer", "height": 20})

        # Audit Findings section
        content.append({"type": "section_header", "text": "Audit Findings"})

        # Add audit findings
        if "findings" in audit_results:
            if isinstance(audit_results["findings"], list):
                for finding in audit_results["findings"]:
                    content.append({"type": "paragraph", "text": f"• {finding}"})
            else:
                content.append({"type": "paragraph", "text": audit_results["findings"]})

        content.append({"type": "spacer", "height": 20})

        # Recommendations section
        content.append({"type": "section_header", "text": "Recommendations"})

        # Add recommendations if present
        if "recommendations" in audit_results:
            if isinstance(audit_results["recommendations"], list):
                for recommendation in audit_results["recommendations"]:
                    content.append({"type": "paragraph", "text": f"• {recommendation}"})
            else:
                content.append(
                    {"type": "paragraph", "text": audit_results["recommendations"]}
                )

        return content

    def _build_business_info_table(
        self, business_data: Dict[str, Any]
    ) -> List[List[str]]:
        """Build business information table data."""
        table_data = [["Field", "Value"]]  # Header row

        # Field name mappings for better display
        field_mappings = {
            "name": "Business Name",
            "industry": "Industry",
            "location": "Location",
            "website": "Website",
            "phone": "Phone",
            "email": "Email",
        }

        # Add business data fields
        for key, value in business_data.items():
            if isinstance(value, (str, int, float)):
                display_name = field_mappings.get(key, key.replace("_", " ").title())
                table_data.append([display_name, str(value)])

        return table_data

    def create_sample_audit_report(
        self, output_path: Optional[str] = None, return_bytes: bool = False
    ) -> Union[str, bytes, None]:
        """
        Create a sample audit report using the template system.

        Args:
            output_path: Path to save the PDF file
            return_bytes: If True, return PDF as bytes instead of saving to file

        Returns:
            Path to generated PDF file, bytes if return_bytes=True, or None
        """
        # Sample business data
        business_data = {
            "company_name": "Sample Corporation",
            "industry": "Technology",
            "employees": 150,
            "revenue": "$5.2M",
            "location": "San Francisco, CA",
        }

        # Sample audit results
        audit_results = {
            "findings": [
                "Strong financial controls in place",
                "IT security measures are adequate",
                "Employee training programs are comprehensive",
            ],
            "recommendations": [
                "Implement quarterly security audits",
                "Update employee handbook",
                "Consider expanding compliance training",
            ],
        }

        return self.generate_audit_report(
            business_data=business_data,
            audit_results=audit_results,
            output_path=output_path,
            return_bytes=return_bytes,
        )

    def generate_report_from_template(
        self,
        report_data,
        template_name: str = "audit_report.html",
        output_path: Optional[str] = None,
        return_bytes: bool = False,
    ) -> Union[str, bytes, None]:
        """
        Generate a PDF report using a template.

        Args:
            report_data: The report data to render
            template_name: Name of the template file to use
            output_path: Path to save the PDF file
            return_bytes: If True, return PDF as bytes instead of saving to file

        Returns:
            Path to generated PDF file, bytes if return_bytes=True, or None
        """
        try:
            # Render the template with report data
            html_content = self.template_engine.render_report(
                report_data, template_name
            )

            # Convert HTML to PDF content structure
            pdf_content = self._convert_html_to_pdf_content(html_content, report_data)

            # Generate the PDF
            return self.generate_document(
                content=pdf_content,
                output_path=output_path,
                return_bytes=return_bytes,
            )

        except Exception as e:
            logger.error(f"Error generating PDF from template: {e}")
            raise PDFGenerationError(f"Failed to generate PDF from template: {e}")

    def _convert_html_to_pdf_content(
        self, html_content: str, report_data
    ) -> List[Dict[str, Any]]:
        """
        Convert HTML content and report data to PDF content structure.

        Args:
            html_content: Rendered HTML content
            report_data: Original report data

        Returns:
            List of content elements for PDF generation
        """
        content = []

        # Add title
        content.append({"type": "title", "text": report_data.title, "style": "title"})

        # Add subtitle if present
        if report_data.subtitle:
            content.append(
                {"type": "subtitle", "text": report_data.subtitle, "level": 2}
            )

        # Add confidential warning if needed
        if report_data.metadata.get("confidential", False):
            content.append(
                {
                    "type": "paragraph",
                    "text": "CONFIDENTIAL - This document contains sensitive information",
                    "style": "warning",
                }
            )

        content.append({"type": "spacer", "height": 20})

        # Process sections
        for section in report_data.sections:
            # Add section heading
            content.append({"type": "section_header", "text": section.title})

            if section.section_type == "text":
                # Add text content
                if isinstance(section.content, list):
                    for paragraph in section.content:
                        content.append({"type": "paragraph", "text": paragraph})
                else:
                    content.append({"type": "paragraph", "text": str(section.content)})

            elif section.section_type == "table":
                # Add table
                if isinstance(section.content, dict) and "headers" in section.content:
                    table_data = [section.content["headers"]]
                    table_data.extend(section.content.get("rows", []))
                    content.append(
                        {"type": "table", "data": table_data, "style": "default"}
                    )

            elif section.section_type == "list":
                # Add bullet list
                content.append(
                    {
                        "type": "bullet_list",
                        "items": (
                            section.content
                            if isinstance(section.content, list)
                            else [str(section.content)]
                        ),
                    }
                )

            elif section.section_type == "chart":
                # Add chart placeholder (charts would need additional implementation)
                content.append(
                    {
                        "type": "paragraph",
                        "text": f"[Chart: {section.content.get('chart_type', 'Unknown')} chart would be displayed here]",
                    }
                )

            content.append({"type": "spacer", "height": 15})

        return content


# Convenience functions for common use cases
def create_audit_report_pdf(
    business_data: Dict[str, Any],
    audit_results: Dict[str, Any],
    output_path: Optional[str] = None,
    config: Optional[PDFConfiguration] = None,
) -> Union[str, bytes]:
    """
    Convenience function to create an audit report PDF.

    Args:
        business_data: Business information
        audit_results: Audit analysis results
        output_path: Path to save the PDF file (if None, returns bytes)
        config: PDF configuration

    Returns:
        Path to generated file or bytes content
    """
    generator = PDFGenerator(config)
    return generator.generate_audit_report(
        business_data, audit_results, output_path, return_bytes=(output_path is None)
    )


def create_simple_pdf(
    content: List[Dict[str, Any]],
    output_path: Optional[str] = None,
    config: Optional[PDFConfiguration] = None,
) -> Union[str, bytes]:
    """
    Convenience function to create a simple PDF from content.

    Args:
        content: List of content elements
        output_path: Path to save the PDF file (if None, returns bytes)
        config: PDF configuration

    Returns:
        Path to generated file or bytes content
    """
    generator = PDFGenerator(config)
    return generator.generate_document(
        content, output_path, return_bytes=(output_path is None)
    )
