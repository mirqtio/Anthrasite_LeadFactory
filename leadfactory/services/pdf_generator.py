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
    permissions: list[PDFPermissions] = None
    watermark: Optional[WatermarkConfig] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []


class CompressionLevel(Enum):
    """PDF compression levels for balancing quality vs file size."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


class ImageQuality(Enum):
    """Image quality settings for PDF optimization."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ORIGINAL = "original"


@dataclass
class OptimizationConfig:
    """Configuration for PDF optimization and compression."""

    compression_level: CompressionLevel = CompressionLevel.MEDIUM
    image_quality: ImageQuality = ImageQuality.MEDIUM
    max_image_width: int = 1200
    max_image_height: int = 1200
    jpeg_quality: int = 85
    enable_image_compression: bool = True
    enable_text_compression: bool = True
    enable_font_subsetting: bool = True
    target_file_size_mb: Optional[float] = None
    enable_size_monitoring: bool = True
    remove_metadata: bool = False
    optimize_for_web: bool = False


class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors."""

    pass


@dataclass
class PDFConfiguration:
    """Configuration class for PDF generation settings."""

    def __init__(
        self,
        page_size: tuple = letter,
        margins: dict[str, float] = None,
        orientation: str = "portrait",
        compression: bool = True,
        optimization_config: Optional[OptimizationConfig] = None,
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
            compression: Enable basic PDF compression (legacy)
            optimization_config: Advanced optimization configuration
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
        self.optimization_config = optimization_config or OptimizationConfig()
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

        # Date style
        self.styles.add(
            ParagraphStyle(
                name="date",
                parent=self.styles["Normal"],
                fontSize=10,
                alignment=TA_LEFT,
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
        content: list[dict[str, Any]],
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

            # Apply compression settings
            self._apply_compression_settings(doc)

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

                # Monitor file size if enabled
                if self.config.optimization_config.enable_size_monitoring:
                    size_mb = len(pdf_bytes) / (1024 * 1024)
                    logger.info(f"Generated PDF size: {size_mb:.2f}MB")

                    # Check target file size
                    target_size = self.config.optimization_config.target_file_size_mb
                    if target_size and size_mb > target_size:
                        logger.warning(
                            f"PDF size ({size_mb:.2f}MB) exceeds target ({target_size}MB)"
                        )

                logger.info("PDF generated successfully as bytes")
                return pdf_bytes
            else:
                # Apply encryption if configured
                if (
                    self.config.security_config
                    and self.config.security_config.enable_encryption
                ) or self.config.encryption:
                    self._encrypt_pdf_file(output_path)

                # Monitor file size if enabled
                if self.config.optimization_config.enable_size_monitoring:
                    metrics = self._monitor_file_size(output_path)
                    logger.info(f"PDF metrics: {metrics}")

                    # Log recommendations if any
                    if metrics.get("recommendations"):
                        for rec in metrics["recommendations"]:
                            logger.info(f"Optimization recommendation: {rec}")

                logger.info(f"PDF generated successfully: {output_path}")
                return output_path

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise PDFGenerationError(f"Failed to generate PDF: {e}")

    def _build_story(self, content: list[dict[str, Any]]) -> list:
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

    def _create_table(self, element: dict[str, Any]) -> Optional[Table]:
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

    def _create_image(self, element: dict[str, Any]) -> Optional[Image]:
        """Create an image from element data."""
        image_path = element.get("path")
        image_data = element.get("data")

        if not image_path and not image_data:
            return None

        try:
            if image_path and os.path.exists(image_path):
                # Optimize image if optimization is enabled
                optimized_path = self._optimize_image(image_path)
                final_path = optimized_path if optimized_path else image_path

                width = element.get("width", 400)
                height = element.get("height", 300)

                # Apply size constraints based on optimization config
                opt_config = self.config.optimization_config
                if opt_config.enable_image_compression:
                    # Respect maximum dimensions from optimization config
                    max_width = min(width, opt_config.max_image_width)
                    max_height = min(height, opt_config.max_image_height)

                    # Maintain aspect ratio
                    if width > max_width or height > max_height:
                        ratio = min(max_width / width, max_height / height)
                        width = int(width * ratio)
                        height = int(height * ratio)
                        logger.info(
                            f"Adjusted image size to {width}x{height} for optimization"
                        )

                return Image(final_path, width=width, height=height)
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
            pdf_writer.add_page(pdf_reader.pages[page_num])

        if (
            self.config.security_config
            and self.config.security_config.enable_encryption
        ) or self.config.encryption:
            if (
                self.config.security_config
                and self.config.security_config.user_password
            ):
                pdf_writer.encrypt(
                    user_password=self.config.security_config.user_password,
                    owner_password=self.config.security_config.owner_password,
                    use_128bit=True,
                )
            elif self.config.password:
                pdf_writer.encrypt(user_password=self.config.password, use_128bit=True)

        encrypted_pdf_bytes = io.BytesIO()
        pdf_writer.write(encrypted_pdf_bytes)
        encrypted_pdf_bytes.seek(0)

        return encrypted_pdf_bytes.getvalue()

    def _encrypt_pdf_file(self, file_path: str):
        """Encrypt PDF file using PyPDF2."""
        pdf_reader = PdfReader(file_path)
        pdf_writer = PdfWriter()

        for page_num in range(len(pdf_reader.pages)):
            pdf_writer.add_page(pdf_reader.pages[page_num])

        if (
            self.config.security_config
            and self.config.security_config.enable_encryption
        ) or self.config.encryption:
            if (
                self.config.security_config
                and self.config.security_config.user_password
            ):
                pdf_writer.encrypt(
                    user_password=self.config.security_config.user_password,
                    owner_password=self.config.security_config.owner_password,
                    use_128bit=True,
                )
            elif self.config.password:
                pdf_writer.encrypt(user_password=self.config.password, use_128bit=True)

        with open(file_path, "wb") as encrypted_file:
            pdf_writer.write(encrypted_file)

    def generate_audit_report(
        self,
        business_data: dict[str, Any],
        audit_results: dict[str, Any],
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
        self, business_data: dict[str, Any], audit_results: dict[str, Any]
    ) -> list[dict[str, Any]]:
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
        self, business_data: dict[str, Any]
    ) -> list[list[str]]:
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

    def generate_from_report_data(
        self,
        report_data,
        template_name: str = "audit_report.html",
        output_path: Optional[str] = None,
        return_bytes: bool = False,
    ) -> Union[str, bytes, None]:
        """
        Generate a PDF report from report data (alias for generate_report_from_template).

        This method is provided for backward compatibility.

        Args:
            report_data: The report data to render
            template_name: Name of the template file to use
            output_path: Path to save the PDF file
            return_bytes: If True, return PDF as bytes instead of saving to file

        Returns:
            Path to generated PDF file, bytes if return_bytes=True, or None
        """
        return self.generate_report_from_template(
            report_data=report_data,
            template_name=template_name,
            output_path=output_path,
            return_bytes=return_bytes,
        )

    def _convert_html_to_pdf_content(
        self, html_content: str, report_data
    ) -> list[dict[str, Any]]:
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

        # Add generated date if available
        if hasattr(report_data, "report_date") and report_data.report_date:
            formatted_date = report_data.report_date.strftime("%B %d, %Y")
            content.append(
                {
                    "type": "paragraph",
                    "text": f"Generated: {formatted_date}",
                    "style": "date",
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
                # Handle different table formats
                if isinstance(section.content, dict):
                    if "headers" in section.content:
                        # Structured table with headers and rows
                        table_data = [section.content["headers"]]
                        table_data.extend(section.content.get("rows", []))
                        content.append(
                            {"type": "table", "data": table_data, "style": "default"}
                        )
                    else:
                        # Key-value table
                        table_data = [["Key", "Value"]]  # Headers
                        for key, value in section.content.items():
                            table_data.append([str(key), str(value)])
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
                # Convert charts to tables for PDF representation
                if isinstance(section.content, dict):
                    chart_type = section.content.get("chart_type", "chart")
                    chart_data = section.content.get("data", [])

                    if chart_data:
                        # Convert chart data to table format
                        if isinstance(chart_data, dict):
                            # Key-value chart data
                            table_data = [["Item", "Value"]]  # Headers
                            for key, value in chart_data.items():
                                table_data.append([str(key), str(value)])
                        elif isinstance(chart_data, list) and chart_data:
                            # List-based chart data
                            if isinstance(chart_data[0], dict):
                                # List of dictionaries - check for common chart patterns
                                if (
                                    "label" in chart_data[0]
                                    and "value" in chart_data[0]
                                ):
                                    # Standard chart format with label/value
                                    table_data = [["Item", "Value"]]  # Standard headers
                                    for item in chart_data:
                                        label = str(item.get("label", ""))
                                        value = str(item.get("value", ""))
                                        table_data.append([label, value])
                                else:
                                    # Generic list of dictionaries
                                    headers = list(chart_data[0].keys())
                                    table_data = [headers]
                                    for item in chart_data:
                                        row = [
                                            str(item.get(header, ""))
                                            for header in headers
                                        ]
                                        table_data.append(row)
                            else:
                                # Simple list
                                table_data = [["Item", "Value"]]
                                for i, item in enumerate(chart_data):
                                    table_data.append([f"Item {i + 1}", str(item)])
                        else:
                            table_data = [["Item", "Value"], ["No data", "N/A"]]

                        content.append(
                            {"type": "table", "data": table_data, "style": "default"}
                        )
                    else:
                        # Fallback for charts without data
                        content.append(
                            {
                                "type": "paragraph",
                                "text": f"[Chart: {chart_type} chart would be displayed here]",
                            }
                        )
                else:
                    # Fallback for non-dict chart content
                    content.append(
                        {
                            "type": "paragraph",
                            "text": "[Chart: chart would be displayed here]",
                        }
                    )

            content.append({"type": "spacer", "height": 15})

        return content

    def _optimize_image(self, image_path: str) -> Optional[str]:
        """
        Optimize an image for PDF embedding based on configuration.

        Args:
            image_path: Path to the original image

        Returns:
            Path to optimized image or None if optimization failed
        """
        try:
            from PIL import Image as PILImage

            opt_config = self.config.optimization_config

            # Skip optimization if disabled
            if not opt_config.enable_image_compression:
                return image_path

            # Open and analyze image
            with PILImage.open(image_path) as img:
                original_size = os.path.getsize(image_path)

                # Convert to RGB if necessary
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")

                # Resize if image is too large
                if (
                    img.width > opt_config.max_image_width
                    or img.height > opt_config.max_image_height
                ):
                    img.thumbnail(
                        (opt_config.max_image_width, opt_config.max_image_height),
                        PILImage.Resampling.LANCZOS,
                    )
                    logger.info(f"Resized image from {img.width}x{img.height}")

                # Determine quality settings based on configuration
                quality_map = {
                    ImageQuality.LOW: 60,
                    ImageQuality.MEDIUM: 85,
                    ImageQuality.HIGH: 95,
                    ImageQuality.ORIGINAL: 100,
                }

                quality = quality_map.get(
                    opt_config.image_quality, opt_config.jpeg_quality
                )

                # Create optimized image path
                base, ext = os.path.splitext(image_path)
                optimized_path = f"{base}_optimized{ext}"

                # Save optimized image
                save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True}
                img.save(optimized_path, **save_kwargs)

                optimized_size = os.path.getsize(optimized_path)
                compression_ratio = (1 - optimized_size / original_size) * 100

                logger.info(f"Image optimized: {compression_ratio:.1f}% size reduction")
                return optimized_path

        except ImportError:
            logger.warning("PIL not available for image optimization")
            return image_path
        except Exception as e:
            logger.warning(f"Image optimization failed: {e}")
            return image_path

    def _monitor_file_size(self, file_path: str) -> dict[str, Any]:
        """
        Monitor and report PDF file size metrics.

        Args:
            file_path: Path to the PDF file

        Returns:
            Dictionary with size metrics and recommendations
        """
        try:
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)

            metrics = {
                "file_size_bytes": file_size,
                "file_size_mb": round(size_mb, 2),
                "optimization_applied": True,
                "compression_level": self.config.optimization_config.compression_level.value,
                "recommendations": [],
            }

            opt_config = self.config.optimization_config

            # Check against target file size
            if (
                opt_config.target_file_size_mb
                and size_mb > opt_config.target_file_size_mb
            ):
                metrics["recommendations"].append(
                    f"File size ({size_mb:.2f}MB) exceeds target ({opt_config.target_file_size_mb}MB)"
                )

                # Suggest optimizations
                if opt_config.image_quality != ImageQuality.LOW:
                    metrics["recommendations"].append("Consider reducing image quality")

                if opt_config.compression_level != CompressionLevel.MAXIMUM:
                    metrics["recommendations"].append(
                        "Consider increasing compression level"
                    )

            # Performance recommendations
            if size_mb > 10:
                metrics["recommendations"].append(
                    "Large file size may impact performance"
                )

            if size_mb > 50:
                metrics["recommendations"].append(
                    "Consider splitting into multiple documents"
                )

            return metrics

        except Exception as e:
            logger.error(f"File size monitoring failed: {e}")
            return {"error": str(e)}

    def _apply_compression_settings(self, doc: SimpleDocTemplate) -> None:
        """
        Apply compression settings to the PDF document.

        Args:
            doc: ReportLab SimpleDocTemplate instance
        """
        opt_config = self.config.optimization_config

        # Configure compression based on level
        if opt_config.compression_level == CompressionLevel.NONE:
            doc.compress = 0
        elif (
            opt_config.compression_level == CompressionLevel.LOW
            or opt_config.compression_level == CompressionLevel.MEDIUM
            or opt_config.compression_level == CompressionLevel.HIGH
            or opt_config.compression_level == CompressionLevel.MAXIMUM
        ):
            doc.compress = 1

        # Note: ReportLab's compression is primarily for text and vector graphics
        # Image compression is handled separately in _optimize_image

        logger.info(f"Applied compression level: {opt_config.compression_level.value}")


# Convenience functions for common use cases
def create_audit_report_pdf(
    business_data: dict[str, Any],
    audit_results: dict[str, Any],
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
    content: list[dict[str, Any]],
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


def create_optimized_pdf(
    content: list[dict[str, Any]],
    output_path: Optional[str] = None,
    compression_level: CompressionLevel = CompressionLevel.HIGH,
    image_quality: ImageQuality = ImageQuality.MEDIUM,
    target_size_mb: Optional[float] = None,
) -> Union[str, bytes, dict[str, Any]]:
    """
    Convenience function to create a highly optimized PDF.

    Args:
        content: List of content elements
        output_path: Path to save the PDF file (if None, returns bytes)
        compression_level: Level of compression to apply
        image_quality: Quality level for image compression
        target_size_mb: Target file size in MB (optional)

    Returns:
        Path to generated file, bytes content, or dict with metrics if optimization enabled
    """
    # Create optimization configuration
    opt_config = OptimizationConfig(
        compression_level=compression_level,
        image_quality=image_quality,
        target_file_size_mb=target_size_mb,
        enable_size_monitoring=True,
        enable_image_compression=True,
        enable_text_compression=True,
    )

    # Create PDF configuration with optimization
    config = PDFConfiguration(optimization_config=opt_config)

    generator = PDFGenerator(config)
    result = generator.generate_document(
        content, output_path, return_bytes=(output_path is None)
    )

    # If file was saved and monitoring is enabled, return metrics too
    if output_path and opt_config.enable_size_monitoring:
        metrics = generator._monitor_file_size(output_path)
        return {"file_path": result, "metrics": metrics}

    return result


def get_optimization_recommendations(file_path: str) -> dict[str, Any]:
    """
    Analyze a PDF file and provide optimization recommendations.

    Args:
        file_path: Path to the PDF file to analyze

    Returns:
        Dictionary with analysis results and recommendations
    """
    # Create a generator with monitoring enabled
    opt_config = OptimizationConfig(enable_size_monitoring=True)
    config = PDFConfiguration(optimization_config=opt_config)
    generator = PDFGenerator(config)

    return generator._monitor_file_size(file_path)
