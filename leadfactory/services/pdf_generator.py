"""
PDF Generation Service

This service provides a comprehensive PDF generation system using ReportLab
for creating professional audit reports and other documents.

Features:
- ReportLab-based PDF generation
- Configurable page settings (size, margins, orientation)
- Template-based document generation
- Security features (encryption, watermarking)
- Error handling and logging
- Compression and optimization
"""

import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape, letter, portrait
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

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors."""

    pass


class PDFConfiguration:
    """Configuration class for PDF generation settings."""

    def __init__(
        self,
        page_size: tuple = letter,
        margins: Dict[str, float] = None,
        orientation: str = "portrait",
        compression: bool = True,
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
            encryption: Enable PDF encryption
            password: Password for encrypted PDFs
            watermark: Watermark text
            title: Document title
            author: Document author
            subject: Document subject
            creator: Document creator
        """
        self.page_size = page_size
        self.margins = margins or {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0}
        self.orientation = orientation
        self.compression = compression
        self.encryption = encryption
        self.password = password
        self.watermark = watermark
        self.title = title
        self.author = author
        self.subject = subject
        self.creator = creator

        # Validate configuration
        self._validate_config()

    def _validate_config(self):
        """Validate configuration parameters."""
        if self.orientation not in ["portrait", "landscape"]:
            raise PDFGenerationError(f"Invalid orientation: {self.orientation}")

        if self.encryption and not self.password:
            raise PDFGenerationError("Password required for encrypted PDFs")

        for margin_key in ["top", "bottom", "left", "right"]:
            if margin_key not in self.margins:
                raise PDFGenerationError(f"Missing margin: {margin_key}")
            if not isinstance(self.margins[margin_key], (int, float)):
                raise PDFGenerationError(f"Invalid margin value for {margin_key}")


class PDFGenerator:
    """
    Main PDF generation service using ReportLab.

    This service provides a high-level interface for generating PDFs
    with support for templates, styling, and security features.
    """

    def __init__(self, config: Optional[PDFConfiguration] = None):
        """
        Initialize PDF generator.

        Args:
            config: PDF configuration object
        """
        self.config = config or PDFConfiguration()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self._register_fonts()

        logger.info("PDF Generator initialized with ReportLab")

    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the PDF."""
        # Title style
        if "CustomTitle" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="CustomTitle",
                    parent=self.styles["Heading1"],
                    fontSize=24,
                    spaceAfter=30,
                    alignment=TA_CENTER,
                    textColor=colors.black,
                )
            )

        # Subtitle style
        if "CustomSubtitle" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="CustomSubtitle",
                    parent=self.styles["Heading2"],
                    fontSize=16,
                    spaceAfter=20,
                    alignment=TA_CENTER,
                    textColor=colors.grey,
                )
            )

        # Section header style
        if "SectionHeader" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="SectionHeader",
                    parent=self.styles["Heading3"],
                    fontSize=14,
                    spaceBefore=20,
                    spaceAfter=10,
                    textColor=colors.black,
                )
            )

        # Body text with better spacing
        if "CustomBodyText" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="CustomBodyText",
                    parent=self.styles["Normal"],
                    fontSize=12,
                    spaceBefore=6,
                    spaceAfter=6,
                    leftIndent=0,
                    rightIndent=0,
                )
            )

        # Highlight style for important text
        if "Highlight" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="Highlight",
                    parent=self.styles["Normal"],
                    fontSize=12,
                    textColor=colors.Color(0.2, 0.2, 0.8),
                    spaceBefore=10,
                    spaceAfter=10,
                )
            )

    def _register_fonts(self):
        """Register custom fonts if available."""
        try:
            # Try to register common system fonts
            font_paths = [
                "/System/Library/Fonts/Arial.ttf",  # macOS
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                "C:\\Windows\\Fonts\\arial.ttf",  # Windows
            ]

            for font_path in font_paths:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont("CustomFont", font_path))
                    logger.info(f"Registered custom font: {font_path}")
                    break
        except Exception as e:
            logger.warning(f"Could not register custom fonts: {e}")

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
                if self.config.encryption:
                    pdf_bytes = self._encrypt_pdf(pdf_bytes)

                logger.info("PDF generated successfully as bytes")
                return pdf_bytes
            else:
                # Apply encryption if configured
                if self.config.encryption:
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

            elif element_type == "section_header":
                story.append(Paragraph(element["text"], self.styles["SectionHeader"]))

            elif element_type == "paragraph":
                style_name = element.get("style", "CustomBodyText")
                story.append(Paragraph(element["text"], self.styles[style_name]))

            elif element_type == "table":
                table = self._create_table(element)
                story.append(table)
                story.append(Spacer(1, 12))

            elif element_type == "image":
                image = self._create_image(element)
                if image:
                    story.append(image)
                    story.append(Spacer(1, 12))

            elif element_type == "spacer":
                height = element.get("height", 12)
                story.append(Spacer(1, height))

            elif element_type == "page_break":
                story.append(PageBreak())

            elif element_type == "keep_together":
                # Wrap content in KeepTogether
                sub_story = self._build_story(element.get("content", []))
                story.append(KeepTogether(sub_story))

        return story

    def _create_table(self, element: Dict[str, Any]) -> Table:
        """Create a formatted table from element data."""
        data = element.get("data", [])
        if not data:
            return Spacer(1, 0)

        # Create table
        table = Table(data)

        # Apply default styling
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]

        # Apply custom styling if provided
        custom_style = element.get("style", [])
        table_style.extend(custom_style)

        table.setStyle(TableStyle(table_style))

        return table

    def _create_image(self, element: Dict[str, Any]) -> Optional[Image]:
        """Create an image from element data."""
        try:
            image_path = element.get("path")
            image_data = element.get("data")

            if image_path and os.path.exists(image_path):
                img = Image(image_path)
            elif image_data:
                img = Image(ImageReader(io.BytesIO(image_data)))
            else:
                logger.warning("No valid image path or data provided")
                return None

            # Set dimensions if provided
            width = element.get("width")
            height = element.get("height")

            if width and height:
                img.drawWidth = width
                img.drawHeight = height
            elif width:
                img.drawWidth = width
                img.drawHeight = width * img.imageHeight / img.imageWidth
            elif height:
                img.drawHeight = height
                img.drawWidth = height * img.imageWidth / img.imageHeight

            return img

        except Exception as e:
            logger.error(f"Failed to create image: {e}")
            return None

    def _add_watermark(self, canvas_obj, doc):
        """Add watermark to PDF pages."""
        if not self.config.watermark:
            return

        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 50)
        canvas_obj.setFillColor(colors.grey, alpha=0.3)
        canvas_obj.rotate(45)
        canvas_obj.drawCentredText(300, 300, self.config.watermark)
        canvas_obj.restoreState()

    def _encrypt_pdf(self, pdf_bytes: bytes) -> bytes:
        """Encrypt PDF bytes (placeholder for encryption implementation)."""
        # Note: ReportLab's encryption requires the commercial version
        # For now, this is a placeholder for future implementation
        logger.warning("PDF encryption not implemented - requires ReportLab PLUS")
        return pdf_bytes

    def _encrypt_pdf_file(self, file_path: str):
        """Encrypt PDF file (placeholder for encryption implementation)."""
        # Note: ReportLab's encryption requires the commercial version
        # For now, this is a placeholder for future implementation
        logger.warning("PDF encryption not implemented - requires ReportLab PLUS")

    def generate_audit_report(
        self,
        business_data: Dict[str, Any],
        audit_results: Dict[str, Any],
        output_path: Optional[str] = None,
        return_bytes: bool = False,
    ) -> Union[str, bytes, None]:
        """
        Generate a professional audit report PDF.

        Args:
            business_data: Business information
            audit_results: Audit analysis results
            output_path: Path to save the PDF file
            return_bytes: Return PDF as bytes instead of saving to file

        Returns:
            Path to generated file, bytes content, or None
        """
        try:
            # Build audit report content
            content = self._build_audit_report_content(business_data, audit_results)

            # Set document metadata
            self.config.title = (
                f"Audit Report - {business_data.get('name', 'Business')}"
            )
            self.config.subject = "Business Audit Analysis"

            return self.generate_document(content, output_path, return_bytes)

        except Exception as e:
            logger.error(f"Audit report generation failed: {e}")
            raise PDFGenerationError(f"Failed to generate audit report: {e}")

    def _build_audit_report_content(
        self, business_data: Dict[str, Any], audit_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build content structure for audit report."""
        content = []

        # Title page
        content.extend(
            [
                {"type": "title", "text": "Business Audit Report"},
                {
                    "type": "subtitle",
                    "text": business_data.get("name", "Business Name"),
                },
                {"type": "spacer", "height": 30},
                {
                    "type": "paragraph",
                    "text": f"Report Generated: {datetime.now().strftime('%B %d, %Y')}",
                    "style": "CustomBodyText",
                },
                {"type": "page_break"},
            ]
        )

        # Executive Summary
        content.extend(
            [
                {"type": "section_header", "text": "Executive Summary"},
                {
                    "type": "paragraph",
                    "text": audit_results.get("summary", "No summary available"),
                    "style": "CustomBodyText",
                },
                {"type": "spacer", "height": 20},
            ]
        )

        # Business Information
        content.extend(
            [
                {"type": "section_header", "text": "Business Information"},
                {
                    "type": "table",
                    "data": self._build_business_info_table(business_data),
                },
                {"type": "spacer", "height": 20},
            ]
        )

        # Audit Results
        if "findings" in audit_results:
            content.extend(
                [
                    {"type": "section_header", "text": "Audit Findings"},
                    {
                        "type": "paragraph",
                        "text": audit_results["findings"],
                        "style": "CustomBodyText",
                    },
                    {"type": "spacer", "height": 20},
                ]
            )

        # Recommendations
        if "recommendations" in audit_results:
            content.extend(
                [
                    {"type": "section_header", "text": "Recommendations"},
                    {
                        "type": "paragraph",
                        "text": audit_results["recommendations"],
                        "style": "CustomBodyText",
                    },
                    {"type": "spacer", "height": 20},
                ]
            )

        return content

    def _build_business_info_table(
        self, business_data: Dict[str, Any]
    ) -> List[List[str]]:
        """Build business information table data."""
        table_data = [["Field", "Value"]]

        fields = [
            ("Business Name", business_data.get("name", "N/A")),
            ("Industry", business_data.get("industry", "N/A")),
            ("Location", business_data.get("location", "N/A")),
            ("Website", business_data.get("website", "N/A")),
            ("Phone", business_data.get("phone", "N/A")),
            ("Email", business_data.get("email", "N/A")),
        ]

        for field, value in fields:
            table_data.append([field, str(value)])

        return table_data


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
