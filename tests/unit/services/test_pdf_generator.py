"""
Unit tests for PDF Generator Service

Tests the PDF generation functionality including:
- Configuration validation
- Document generation
- Audit report generation
- Error handling
- Content building
"""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.services.pdf_generator import (
    CompressionLevel,
    ImageQuality,
    OptimizationConfig,
    PDFConfiguration,
    PDFGenerationError,
    PDFGenerator,
    create_audit_report_pdf,
    create_optimized_pdf,
    create_simple_pdf,
    get_optimization_recommendations,
)


class TestPDFConfiguration:
    """Test PDFConfiguration class."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = PDFConfiguration()

        assert config.orientation == "portrait"
        assert config.compression is True
        assert config.encryption is False
        assert config.password is None
        assert config.watermark is None
        assert config.creator == "Anthrasite LeadFactory"
        assert "top" in config.margins
        assert "bottom" in config.margins
        assert "left" in config.margins
        assert "right" in config.margins

    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = PDFConfiguration(
            orientation="landscape",
            compression=False,
            encryption=True,
            password="test123",
            watermark="CONFIDENTIAL",
            title="Test Document",
            author="Test Author",
        )

        assert config.orientation == "landscape"
        assert config.compression is False
        assert config.encryption is True
        assert config.password == "test123"
        assert config.watermark == "CONFIDENTIAL"
        assert config.title == "Test Document"
        assert config.author == "Test Author"

    def test_invalid_orientation(self):
        """Test invalid orientation raises error."""
        with pytest.raises(PDFGenerationError, match="Invalid orientation"):
            PDFConfiguration(orientation="invalid")

    def test_encryption_without_password(self):
        """Test encryption without password raises error."""
        with pytest.raises(PDFGenerationError, match="Password required"):
            PDFConfiguration(encryption=True)

    def test_missing_margins(self):
        """Test missing margins raise error."""
        with pytest.raises(PDFGenerationError, match="Missing margin"):
            PDFConfiguration(margins={"top": 1.0})  # Missing other margins

    def test_invalid_margin_values(self):
        """Test invalid margin values raise error."""
        with pytest.raises(PDFGenerationError, match="Invalid margin value"):
            PDFConfiguration(
                margins={"top": 1.0, "bottom": 1.0, "left": "invalid", "right": 1.0}
            )


class TestPDFGenerator:
    """Test PDFGenerator class."""

    @pytest.fixture
    def pdf_generator(self):
        """Create PDF generator instance for testing."""
        config = PDFConfiguration(title="Test Document")
        return PDFGenerator(config)

    @pytest.fixture
    def sample_content(self):
        """Sample content for testing."""
        return [
            {"type": "title", "text": "Test Document"},
            {"type": "paragraph", "text": "This is a test paragraph."},
            {"type": "table", "data": [["Header 1", "Header 2"], ["Row 1", "Row 2"]]},
            {"type": "spacer", "height": 20},
        ]

    def test_initialization(self, pdf_generator):
        """Test PDF generator initialization."""
        assert pdf_generator.config.title == "Test Document"
        assert hasattr(pdf_generator, "styles")
        assert "CustomTitle" in pdf_generator.styles
        assert "BodyText" in pdf_generator.styles

    def test_custom_styles_creation(self, pdf_generator):
        """Test custom styles are created properly."""
        styles = pdf_generator.styles

        # Check custom styles exist
        assert "CustomTitle" in styles
        assert "CustomSubtitle" in styles
        assert "SectionHeader" in styles
        assert "CustomBodyText" in styles
        assert "Highlight" in styles

        # Check style properties
        title_style = styles["CustomTitle"]
        assert title_style.fontSize == 24
        assert title_style.spaceAfter == 30

    @patch("leadfactory.services.pdf_generator.SimpleDocTemplate")
    def test_generate_document_return_bytes(
        self, mock_doc, pdf_generator, sample_content
    ):
        """Test generating document and returning bytes."""
        # Mock the document and its build method
        mock_doc_instance = Mock()
        mock_doc.return_value = mock_doc_instance

        with patch("io.BytesIO") as mock_bytesio:
            mock_buffer = Mock()
            mock_buffer.getvalue.return_value = b"fake_pdf_content"
            mock_bytesio.return_value = mock_buffer

            result = pdf_generator.generate_document(sample_content, return_bytes=True)

            assert result == b"fake_pdf_content"
            mock_doc_instance.build.assert_called_once()
            mock_buffer.getvalue.assert_called_once()

    @patch("leadfactory.services.pdf_generator.SimpleDocTemplate")
    @patch("os.makedirs")
    def test_generate_document_save_file(
        self, mock_makedirs, mock_doc, pdf_generator, sample_content
    ):
        """Test generating document and saving to file."""
        mock_doc_instance = Mock()
        mock_doc.return_value = mock_doc_instance

        output_path = "/tmp/test.pdf"
        result = pdf_generator.generate_document(
            sample_content, output_path=output_path
        )

        assert result == output_path
        mock_makedirs.assert_called_once()
        mock_doc_instance.build.assert_called_once()

    def test_generate_document_no_output_path(self, pdf_generator, sample_content):
        """Test error when no output path provided and not returning bytes."""
        with pytest.raises(PDFGenerationError, match="Output path required"):
            pdf_generator.generate_document(sample_content, return_bytes=False)

    def test_build_story_title(self, pdf_generator):
        """Test building story with title element."""
        content = [{"type": "title", "text": "Test Title"}]
        story = pdf_generator._build_story(content)

        assert len(story) == 2  # Paragraph + Spacer
        # First element should be a Paragraph with title text
        assert hasattr(story[0], "text")

    def test_build_story_paragraph(self, pdf_generator):
        """Test building story with paragraph element."""
        content = [
            {"type": "paragraph", "text": "Test paragraph", "style": "CustomBodyText"}
        ]
        story = pdf_generator._build_story(content)

        assert len(story) == 1
        assert hasattr(story[0], "text")

    def test_build_story_table(self, pdf_generator):
        """Test building story with table element."""
        content = [
            {"type": "table", "data": [["Header 1", "Header 2"], ["Row 1", "Row 2"]]}
        ]
        story = pdf_generator._build_story(content)

        assert len(story) == 2  # Table + Spacer

    def test_build_story_spacer(self, pdf_generator):
        """Test building story with spacer element."""
        content = [{"type": "spacer", "height": 25}]
        story = pdf_generator._build_story(content)

        assert len(story) == 1

    def test_build_story_page_break(self, pdf_generator):
        """Test building story with page break element."""
        content = [{"type": "page_break"}]
        story = pdf_generator._build_story(content)

        assert len(story) == 1

    def test_create_table_empty_data(self, pdf_generator):
        """Test creating table with empty data."""
        element = {"type": "table", "data": []}
        table = pdf_generator._create_table(element)

        # Should return a spacer when no data
        assert hasattr(table, "height")

    def test_create_table_with_data(self, pdf_generator):
        """Test creating table with data."""
        element = {
            "type": "table",
            "data": [["Header 1", "Header 2"], ["Row 1", "Row 2"]],
        }
        table = pdf_generator._create_table(element)

        assert hasattr(table, "_argW")  # Table attribute

    @patch("os.path.exists")
    def test_create_image_with_path(self, mock_exists, pdf_generator):
        """Test creating image with file path."""
        mock_exists.return_value = True

        with patch("leadfactory.services.pdf_generator.Image") as mock_image:
            mock_image_instance = Mock()
            mock_image_instance.imageHeight = 100
            mock_image_instance.imageWidth = 200
            mock_image.return_value = mock_image_instance

            element = {"type": "image", "path": "/path/to/image.jpg", "width": 150}

            result = pdf_generator._create_image(element)

            assert result is not None
            mock_image.assert_called_once()

    def test_create_image_no_path_or_data(self, pdf_generator):
        """Test creating image without path or data."""
        element = {"type": "image"}
        result = pdf_generator._create_image(element)

        assert result is None

    def test_build_business_info_table(self, pdf_generator):
        """Test building business information table."""
        business_data = {
            "name": "Test Business",
            "industry": "Technology",
            "location": "San Francisco",
            "website": "https://test.com",
            "phone": "555-1234",
            "email": "test@test.com",
        }

        table_data = pdf_generator._build_business_info_table(business_data)

        assert len(table_data) == 7  # Header + 6 data rows
        assert table_data[0] == ["Field", "Value"]
        assert table_data[1] == ["Business Name", "Test Business"]
        assert table_data[2] == ["Industry", "Technology"]

    def test_build_audit_report_content(self, pdf_generator):
        """Test building audit report content structure."""
        business_data = {"name": "Test Business", "industry": "Technology"}
        audit_results = {
            "summary": "Test summary",
            "findings": "Test findings",
            "recommendations": "Test recommendations",
        }

        content = pdf_generator._build_audit_report_content(
            business_data, audit_results
        )

        # Should have multiple sections
        assert len(content) > 10

        # Check for key sections
        section_headers = [
            item for item in content if item.get("type") == "section_header"
        ]
        section_texts = [item["text"] for item in section_headers]

        assert "Executive Summary" in section_texts
        assert "Business Information" in section_texts
        assert "Audit Findings" in section_texts
        assert "Recommendations" in section_texts

    @patch("leadfactory.services.pdf_generator.PDFGenerator.generate_document")
    def test_generate_audit_report(self, mock_generate, pdf_generator):
        """Test generating audit report."""
        mock_generate.return_value = "/tmp/audit_report.pdf"

        business_data = {"name": "Test Business"}
        audit_results = {"summary": "Test summary"}

        result = pdf_generator.generate_audit_report(
            business_data, audit_results, output_path="/tmp/audit_report.pdf"
        )

        assert result == "/tmp/audit_report.pdf"
        mock_generate.assert_called_once()

        # Check that document metadata was set
        assert pdf_generator.config.title == "Audit Report - Test Business"
        assert pdf_generator.config.subject == "Business Audit Analysis"

    @patch("leadfactory.services.pdf_generator.PDFGenerator.generate_document")
    def test_generate_audit_report_error_handling(self, mock_generate, pdf_generator):
        """Test audit report generation error handling."""
        mock_generate.side_effect = Exception("Test error")

        business_data = {"name": "Test Business"}
        audit_results = {"summary": "Test summary"}

        with pytest.raises(PDFGenerationError, match="Failed to generate audit report"):
            pdf_generator.generate_audit_report(business_data, audit_results)


class TestConvenienceFunctions:
    """Test convenience functions."""

    @patch("leadfactory.services.pdf_generator.PDFGenerator")
    def test_create_audit_report_pdf(self, mock_generator_class):
        """Test create_audit_report_pdf convenience function."""
        mock_generator = Mock()
        mock_generator.generate_audit_report.return_value = "/tmp/report.pdf"
        mock_generator_class.return_value = mock_generator

        business_data = {"name": "Test Business"}
        audit_results = {"summary": "Test summary"}

        result = create_audit_report_pdf(
            business_data, audit_results, output_path="/tmp/report.pdf"
        )

        assert result == "/tmp/report.pdf"
        mock_generator_class.assert_called_once()
        mock_generator.generate_audit_report.assert_called_once_with(
            business_data, audit_results, "/tmp/report.pdf", return_bytes=False
        )

    @patch("leadfactory.services.pdf_generator.PDFGenerator")
    def test_create_audit_report_pdf_return_bytes(self, mock_generator_class):
        """Test create_audit_report_pdf returning bytes."""
        mock_generator = Mock()
        mock_generator.generate_audit_report.return_value = b"pdf_bytes"
        mock_generator_class.return_value = mock_generator

        business_data = {"name": "Test Business"}
        audit_results = {"summary": "Test summary"}

        result = create_audit_report_pdf(
            business_data,
            audit_results,
            output_path=None,  # Should return bytes
        )

        assert result == b"pdf_bytes"
        mock_generator.generate_audit_report.assert_called_once_with(
            business_data, audit_results, None, return_bytes=True
        )

    @patch("leadfactory.services.pdf_generator.PDFGenerator")
    def test_create_simple_pdf(self, mock_generator_class):
        """Test create_simple_pdf convenience function."""
        mock_generator = Mock()
        mock_generator.generate_document.return_value = "/tmp/simple.pdf"
        mock_generator_class.return_value = mock_generator

        content = [{"type": "title", "text": "Test"}]

        result = create_simple_pdf(content, output_path="/tmp/simple.pdf")

        assert result == "/tmp/simple.pdf"
        mock_generator_class.assert_called_once()
        mock_generator.generate_document.assert_called_once_with(
            content, "/tmp/simple.pdf", return_bytes=False
        )


class TestOptimizationConfig:
    """Test OptimizationConfig class."""

    def test_default_optimization_config(self):
        """Test default optimization configuration values."""
        config = OptimizationConfig()

        assert config.compression_level == CompressionLevel.MEDIUM
        assert config.image_quality == ImageQuality.MEDIUM
        assert config.max_image_width == 1200
        assert config.max_image_height == 1200
        assert config.jpeg_quality == 85
        assert config.enable_image_compression is True
        assert config.enable_text_compression is True
        assert config.enable_font_subsetting is True
        assert config.target_file_size_mb is None
        assert config.enable_size_monitoring is True
        assert config.remove_metadata is False
        assert config.optimize_for_web is False

    def test_custom_optimization_config(self):
        """Test custom optimization configuration values."""
        config = OptimizationConfig(
            compression_level=CompressionLevel.HIGH,
            image_quality=ImageQuality.LOW,
            max_image_width=800,
            max_image_height=600,
            jpeg_quality=70,
            target_file_size_mb=5.0,
            optimize_for_web=True,
        )

        assert config.compression_level == CompressionLevel.HIGH
        assert config.image_quality == ImageQuality.LOW
        assert config.max_image_width == 800
        assert config.max_image_height == 600
        assert config.jpeg_quality == 70
        assert config.target_file_size_mb == 5.0
        assert config.optimize_for_web is True

    def test_compression_level_enum(self):
        """Test CompressionLevel enum values."""
        assert CompressionLevel.NONE.value == "none"
        assert CompressionLevel.LOW.value == "low"
        assert CompressionLevel.MEDIUM.value == "medium"
        assert CompressionLevel.HIGH.value == "high"
        assert CompressionLevel.MAXIMUM.value == "maximum"

    def test_image_quality_enum(self):
        """Test ImageQuality enum values."""
        assert ImageQuality.LOW.value == "low"
        assert ImageQuality.MEDIUM.value == "medium"
        assert ImageQuality.HIGH.value == "high"
        assert ImageQuality.ORIGINAL.value == "original"


class TestPDFOptimization:
    """Test PDF optimization features."""

    @pytest.fixture
    def optimized_config(self):
        """Create optimized PDF configuration for testing."""
        opt_config = OptimizationConfig(
            compression_level=CompressionLevel.HIGH,
            image_quality=ImageQuality.MEDIUM,
            enable_size_monitoring=True,
            target_file_size_mb=2.0,
        )
        return PDFConfiguration(optimization_config=opt_config)

    @pytest.fixture
    def pdf_generator_optimized(self, optimized_config):
        """Create PDF generator with optimization for testing."""
        return PDFGenerator(optimized_config)

    def test_optimization_config_integration(self, optimized_config):
        """Test optimization config is properly integrated."""
        assert optimized_config.optimization_config is not None
        assert (
            optimized_config.optimization_config.compression_level
            == CompressionLevel.HIGH
        )
        assert optimized_config.optimization_config.enable_size_monitoring is True

    @patch("leadfactory.services.pdf_generator.os.path.getsize")
    def test_monitor_file_size(self, mock_getsize, pdf_generator_optimized):
        """Test file size monitoring functionality."""
        mock_getsize.return_value = 1024 * 1024  # 1MB

        metrics = pdf_generator_optimized._monitor_file_size("/fake/path.pdf")

        assert "file_size_bytes" in metrics
        assert "file_size_mb" in metrics
        assert metrics["file_size_mb"] == 1.0
        assert "compression_level" in metrics
        assert metrics["compression_level"] == "high"

    @patch("leadfactory.services.pdf_generator.os.path.getsize")
    def test_monitor_file_size_with_target_exceeded(
        self, mock_getsize, pdf_generator_optimized
    ):
        """Test file size monitoring when target is exceeded."""
        mock_getsize.return_value = 5 * 1024 * 1024  # 5MB (exceeds 2MB target)

        metrics = pdf_generator_optimized._monitor_file_size("/fake/path.pdf")

        assert metrics["file_size_mb"] == 5.0
        assert len(metrics["recommendations"]) > 0
        assert any("exceeds target" in rec for rec in metrics["recommendations"])

    @patch("leadfactory.services.pdf_generator.os.path.getsize")
    @patch("leadfactory.services.pdf_generator.os.path.exists")
    def test_optimize_image(self, mock_exists, mock_getsize, pdf_generator_optimized):
        """Test image optimization functionality."""
        mock_exists.return_value = True
        mock_getsize.side_effect = [2048, 1024]  # Original: 2KB, Optimized: 1KB

        # Mock PIL Image import
        with patch("builtins.__import__") as mock_import:
            mock_pil_module = Mock()
            mock_img = Mock()
            mock_img.mode = "RGB"
            mock_img.width = 1600
            mock_img.height = 1200

            # Create a proper context manager mock
            mock_context_manager = Mock()
            mock_context_manager.__enter__ = Mock(return_value=mock_img)
            mock_context_manager.__exit__ = Mock(return_value=None)
            mock_pil_module.Image.open.return_value = mock_context_manager

            def import_side_effect(name, *args, **kwargs):
                if name == "PIL":
                    return mock_pil_module
                return __import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = pdf_generator_optimized._optimize_image("/fake/image.jpg")

            assert result is not None
            assert "_optimized" in result
            mock_img.thumbnail.assert_called_once()
            mock_img.save.assert_called_once()

    def test_optimize_image_disabled(self, pdf_generator_optimized):
        """Test image optimization when disabled."""
        pdf_generator_optimized.config.optimization_config.enable_image_compression = (
            False
        )

        result = pdf_generator_optimized._optimize_image("/fake/image.jpg")

        assert result == "/fake/image.jpg"

    def test_apply_compression_settings(self, pdf_generator_optimized):
        """Test compression settings application."""
        mock_doc = Mock()

        pdf_generator_optimized._apply_compression_settings(mock_doc)

        assert mock_doc.compress == 1  # High compression should enable compression

    @patch("leadfactory.services.pdf_generator.SimpleDocTemplate")
    def test_generate_document_with_optimization(
        self, mock_doc_class, pdf_generator_optimized
    ):
        """Test document generation with optimization features."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc

        content = [{"type": "paragraph", "text": "Test content"}]

        with patch.object(
            pdf_generator_optimized, "_apply_compression_settings"
        ) as mock_compress:
            pdf_generator_optimized.generate_document(content, return_bytes=True)

            mock_compress.assert_called_once_with(mock_doc)

    @patch("leadfactory.services.pdf_generator.os.path.exists")
    def test_create_image_with_optimization(self, mock_exists, pdf_generator_optimized):
        """Test image creation with optimization."""
        mock_exists.return_value = True

        with patch.object(pdf_generator_optimized, "_optimize_image") as mock_optimize:
            mock_optimize.return_value = "/fake/optimized.jpg"

            element = {"path": "/fake/image.jpg", "width": 2000, "height": 1500}
            pdf_generator_optimized._create_image(element)

            mock_optimize.assert_called_once_with("/fake/image.jpg")


class TestOptimizedConvenienceFunctions:
    """Test optimized convenience functions."""

    @patch("leadfactory.services.pdf_generator.PDFGenerator")
    def test_create_optimized_pdf(self, mock_generator_class):
        """Test create_optimized_pdf convenience function."""
        mock_generator = Mock()
        mock_generator_class.return_value = mock_generator
        mock_generator.generate_document.return_value = b"pdf_bytes"

        content = [{"type": "paragraph", "text": "Test"}]
        result = create_optimized_pdf(
            content,
            compression_level=CompressionLevel.HIGH,
            image_quality=ImageQuality.LOW,
        )

        assert result == b"pdf_bytes"
        mock_generator_class.assert_called_once()
        mock_generator.generate_document.assert_called_once()

    @patch("leadfactory.services.pdf_generator.PDFGenerator")
    def test_create_optimized_pdf_with_file_output(self, mock_generator_class):
        """Test create_optimized_pdf with file output and metrics."""
        mock_generator = Mock()
        mock_generator_class.return_value = mock_generator
        mock_generator.generate_document.return_value = "/fake/output.pdf"
        mock_generator._monitor_file_size.return_value = {"file_size_mb": 1.5}

        content = [{"type": "paragraph", "text": "Test"}]
        result = create_optimized_pdf(content, output_path="/fake/output.pdf")

        assert isinstance(result, dict)
        assert "file_path" in result
        assert "metrics" in result
        assert result["file_path"] == "/fake/output.pdf"

    @patch("leadfactory.services.pdf_generator.PDFGenerator")
    def test_get_optimization_recommendations(self, mock_generator_class):
        """Test get_optimization_recommendations function."""
        mock_generator = Mock()
        mock_generator_class.return_value = mock_generator
        mock_generator._monitor_file_size.return_value = {
            "file_size_mb": 5.0,
            "recommendations": ["Consider reducing image quality"],
        }

        result = get_optimization_recommendations("/fake/file.pdf")

        assert result["file_size_mb"] == 5.0
        assert len(result["recommendations"]) > 0
        mock_generator._monitor_file_size.assert_called_once_with("/fake/file.pdf")


class TestIntegration:
    """Integration tests for PDF generation."""

    def test_real_pdf_generation(self):
        """Test actual PDF generation with ReportLab."""
        # Skip if ReportLab not available
        pytest.importorskip("reportlab")

        config = PDFConfiguration(title="Integration Test")
        generator = PDFGenerator(config)

        content = [
            {"type": "title", "text": "Integration Test Document"},
            {
                "type": "paragraph",
                "text": "This is a test paragraph for integration testing.",
            },
            {
                "type": "table",
                "data": [
                    ["Column 1", "Column 2"],
                    ["Data 1", "Data 2"],
                    ["Data 3", "Data 4"],
                ],
            },
        ]

        # Generate PDF as bytes
        pdf_bytes = generator.generate_document(content, return_bytes=True)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")  # PDF header

    def test_real_audit_report_generation(self):
        """Test actual audit report generation."""
        # Skip if ReportLab not available
        pytest.importorskip("reportlab")

        business_data = {
            "name": "Test Business Inc.",
            "industry": "Technology",
            "location": "San Francisco, CA",
            "website": "https://testbusiness.com",
            "phone": "(555) 123-4567",
            "email": "contact@testbusiness.com",
        }

        audit_results = {
            "summary": "This business shows strong digital presence with opportunities for improvement in SEO and social media engagement.",
            "findings": "The website has good technical performance but lacks comprehensive meta descriptions and structured data.",
            "recommendations": "Implement structured data markup, optimize meta descriptions, and develop a content marketing strategy.",
        }

        pdf_bytes = create_audit_report_pdf(
            business_data,
            audit_results,
            output_path=None,  # Return bytes
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")  # PDF header

    def test_error_handling_with_invalid_content(self):
        """Test error handling with invalid content."""
        generator = PDFGenerator()

        # Test with content that might cause errors
        invalid_content = [
            {"type": "unknown_type", "text": "This should be handled gracefully"}
        ]

        # Should not raise an error, just skip unknown types
        pdf_bytes = generator.generate_document(invalid_content, return_bytes=True)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0


if __name__ == "__main__":
    pytest.main([__file__])
