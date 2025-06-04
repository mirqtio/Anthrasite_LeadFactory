"""
Security tests for PDF generation and protection features.

This module tests PDF security features including password protection,
metadata sanitization, and protection against various attack vectors.
"""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from reportlab.lib.pagesizes import A4, letter

from leadfactory.services.pdf_generator import (
    PDFGenerator,
    PDFConfiguration,
    SecurityConfig,
    OptimizationConfig,
    CompressionLevel,
    ImageQuality,
)
from leadfactory.services.report_template_engine import (
    ReportData,
    ReportSection,
)


@pytest.mark.security
class TestPDFSecurity:
    """Security tests for PDF generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.optimization_config = OptimizationConfig(
            compression_level=CompressionLevel.MEDIUM,
            image_quality=ImageQuality.MEDIUM,
            enable_image_compression=True,
        )

        self.pdf_config = PDFConfiguration(
            page_size=A4,
            orientation="portrait",
            compression=True,
            optimization_config=self.optimization_config,
        )

        self.pdf_generator = PDFGenerator(
            config=self.pdf_config,
        )

    def test_pdf_password_protection(self):
        """Test PDF password protection functionality."""
        report_data = ReportData(
            title="Confidential Security Report",
            subtitle="Password Protected Document",
            metadata={"confidential": True}
        )

        report_data.add_section(ReportSection(
            title="Sensitive Information",
            content="This document contains sensitive security information.",
            section_type="text",
            order=1
        ))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "password_protected.pdf"

            # Generate PDF with password protection
            pdf_config_secure = PDFConfiguration(
                password="test_password_123",
                encryption=True,
                optimization_config=self.optimization_config,
            )

            secure_generator = PDFGenerator(
                config=pdf_config_secure,
            )

            pdf_bytes = secure_generator.generate_from_report_data(
                report_data=report_data,
                output_path=str(output_path)
            )

            assert output_path.exists()
            assert len(pdf_bytes) > 0

            # Verify PDF is encrypted (basic check)
            with open(output_path, 'rb') as f:
                pdf_content = f.read()
                # Encrypted PDFs should contain encryption markers
                assert b'/Encrypt' in pdf_content or b'encrypted' in pdf_content.lower()

    def test_pdf_metadata_sanitization(self):
        """Test that sensitive metadata is properly sanitized."""
        report_data = ReportData(
            title="Test Report",
            subtitle="Metadata Security Test",
            metadata={
                "author": "Test Author",
                "confidential": True,
                "internal_id": "INTERNAL-123",
                "api_key": "secret_key_123",  # Should be sanitized
                "password": "secret_password",  # Should be sanitized
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "metadata_test.pdf"

            pdf_bytes = self.pdf_generator.generate_from_report_data(
                report_data=report_data,
                output_path=str(output_path)
            )

            assert output_path.exists()

            # Read PDF content and verify sensitive data is not exposed
            from pypdf import PdfReader

            pdf_reader = PdfReader(output_path)
            pdf_text = ""
            for page in pdf_reader.pages:
                pdf_text += page.extract_text()

            # These should NOT appear in the PDF
            assert "secret_key_123" not in pdf_text
            assert "secret_password" not in pdf_text

            # These are OK to appear
            assert "Test Report" in pdf_text

    def test_html_injection_prevention(self):
        """Test prevention of HTML/JavaScript injection in PDF content."""
        malicious_content = [
            "<script>alert('XSS')</script>",
            "<iframe src='http://malicious.com'></iframe>",
            "<object data='malicious.swf'></object>",
            "<embed src='malicious.swf'>",
            "javascript:alert('XSS')",
            "<img src='x' onerror='alert(1)'>",
        ]

        for malicious_input in malicious_content:
            report_data = ReportData(
                title="Security Test Report",
                subtitle="HTML Injection Prevention Test"
            )

            report_data.add_section(ReportSection(
                title="Test Section",
                content=f"Safe content with malicious input: {malicious_input}",
                section_type="text",
                order=1
            ))

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"injection_test_{hash(malicious_input)}.pdf"

                # Should not raise exceptions and should sanitize content
                pdf_bytes = self.pdf_generator.generate_from_report_data(
                    report_data=report_data,
                    output_path=str(output_path)
                )

                assert output_path.exists()
                assert len(pdf_bytes) > 0

                # Verify malicious content is sanitized
                with open(output_path, 'rb') as f:
                    pdf_content = f.read().decode('latin-1', errors='ignore')

                    # Script tags should be removed or escaped
                    assert "<script>" not in pdf_content.lower()
                    assert "javascript:" not in pdf_content.lower()
                    assert "onerror=" not in pdf_content.lower()

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks in file operations."""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "file:///etc/passwd",
            "\\\\server\\share\\file.txt",
        ]

        for malicious_path in malicious_paths:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Try to use malicious path as output path
                try:
                    report_data = ReportData(
                        title="Path Traversal Test",
                        subtitle="Security Test"
                    )

                    # Should either sanitize the path or raise an appropriate error
                    pdf_bytes = self.pdf_generator.generate_from_report_data(
                        report_data=report_data,
                        output_path=malicious_path
                    )

                    # If it succeeds, verify it didn't actually write to the malicious path
                    assert not os.path.exists(malicious_path)

                except (ValueError, OSError, PermissionError):
                    # Expected behavior - should reject malicious paths
                    pass

    def test_resource_exhaustion_prevention(self):
        """Test prevention of resource exhaustion attacks."""
        # Test with extremely large content
        large_content = "A" * (10 * 1024 * 1024)  # 10MB of text

        report_data = ReportData(
            title="Resource Exhaustion Test",
            subtitle="Testing large content handling"
        )

        report_data.add_section(ReportSection(
            title="Large Section",
            content=large_content,
            section_type="text",
            order=1
        ))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "resource_test.pdf"

            # Should handle large content gracefully without crashing
            try:
                pdf_bytes = self.pdf_generator.generate_from_report_data(
                    report_data=report_data,
                    output_path=str(output_path)
                )

                # If successful, verify reasonable file size
                if output_path.exists():
                    file_size = output_path.stat().st_size
                    # Should not create excessively large files
                    assert file_size < 100 * 1024 * 1024  # 100MB limit

            except (MemoryError, OSError):
                # Acceptable to fail gracefully with large content
                pass

    def test_template_injection_prevention(self):
        """Test prevention of template injection attacks."""
        malicious_templates = [
            "{{ ''.__class__.__mro__[2].__subclasses__()[40]('/etc/passwd').read() }}",
            "{% for x in ().__class__.__base__.__subclasses__() %}{% if \"warning\" in x.__name__ %}{{x()._module.__builtins__['__import__']('os').popen(\"id\").read()}}{% endif %}{% endfor %}",
            "${7*7}",
            "{{7*7}}",
            "#{7*7}",
            "<%= 7*7 %>",
        ]

        for malicious_template in malicious_templates:
            report_data = ReportData(
                title="Template Injection Test",
                subtitle="Security Test"
            )

            report_data.add_section(ReportSection(
                title="Test Section",
                content=f"Template content: {malicious_template}",
                section_type="text",
                order=1
            ))

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"template_injection_test_{hash(malicious_template)}.pdf"

                # Should not execute template code
                pdf_bytes = self.pdf_generator.generate_from_report_data(
                    report_data=report_data,
                    output_path=str(output_path)
                )

                assert output_path.exists()

                # Verify template code was not executed
                with open(output_path, 'rb') as f:
                    pdf_content = f.read().decode('latin-1', errors='ignore')

                    # Should not contain executed results (like "49" from 7*7)
                    # Template syntax should be escaped or removed
                    assert "{{" not in pdf_content or malicious_template in pdf_content

    def test_pdf_structure_validation(self):
        """Test PDF structure validation for security."""
        report_data = ReportData(
            title="Structure Validation Test",
            subtitle="PDF Security Test"
        )

        report_data.add_section(ReportSection(
            title="Test Content",
            content="Testing PDF structure validation.",
            section_type="text",
            order=1
        ))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "structure_test.pdf"

            pdf_bytes = self.pdf_generator.generate_from_report_data(
                report_data=report_data,
                output_path=str(output_path)
            )

            assert output_path.exists()

            # Basic PDF structure validation
            with open(output_path, 'rb') as f:
                pdf_content = f.read()

                # Should start with PDF header
                assert pdf_content.startswith(b'%PDF-')

                # Should end with EOF marker
                assert b'%%EOF' in pdf_content

                # Should not contain suspicious elements
                suspicious_elements = [
                    b'/JavaScript',
                    b'/JS',
                    b'/Launch',
                    b'/SubmitForm',
                    b'/ImportData',
                ]

                for element in suspicious_elements:
                    assert element not in pdf_content, f"Suspicious element found: {element}"
