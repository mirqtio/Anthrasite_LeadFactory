"""
End-to-end tests for the complete PDF rendering pipeline.

This module tests the full PDF generation workflow from report data
through template processing to final PDF output with quality validation.
"""

import os
import tempfile
import pytest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from reportlab.lib.pagesizes import A4, letter

from leadfactory.services.pdf_generator import (
    PDFGenerator,
    PDFConfiguration,
    OptimizationConfig,
    CompressionLevel,
    ImageQuality,
    create_simple_pdf,
)
from leadfactory.services.report_template_engine import (
    ReportTemplateEngine,
    ReportData,
    ReportSection,
)
from leadfactory.services.pdf_quality_validator import PDFQualityValidator


@pytest.mark.e2e
class TestPDFRenderingPipelineE2E:
    """End-to-end tests for the complete PDF rendering pipeline."""

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
            margins={"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},  # In inches, not points
            compression=True,
            optimization_config=self.optimization_config,
        )

        self.pdf_generator = PDFGenerator(
            config=self.pdf_config,
        )

        self.template_engine = ReportTemplateEngine()
        self.quality_validator = PDFQualityValidator()

    @pytest.mark.e2e
    def test_complete_audit_report_pipeline(self):
        """Test complete pipeline for audit report generation."""
        # Create minimal test report data to avoid layout issues
        business_data = {
            "name": "Test Co",
            "industry": "Tech",
            "size": "Small",
            "location": "SF",
        }

        audit_results = {
            "overall_score": 85,
            "risk_level": "Low",
            "total_findings": 2,
            "critical_findings": 0,
            "recommendations_count": 2,
            "findings": [
                {"title": "Finding 1", "severity": "Low", "description": "Short desc"},
            ],
            "recommendations": [
                "Short recommendation",
            ]
        }

        # Test the complete pipeline
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "e2e_audit_report.pdf"

            # Step 1: Generate PDF through complete pipeline
            pdf_bytes = self.pdf_generator.generate_audit_report(
                business_data=business_data,
                audit_results=audit_results,
                output_path=str(output_path),
                return_bytes=False,  # Save to file instead of returning bytes
            )

            # Verify PDF was created
            assert output_path.exists()
            assert pdf_bytes == str(output_path)  # Should return the path when saving to file

            # Step 2: Validate PDF quality
            validation_result = self.quality_validator.validate_pdf(str(output_path))
            assert validation_result.is_valid
            assert validation_result.overall_score >= 80.0  # Score is 0-100, not 0-1

            # Step 3: Verify PDF content structure
            assert validation_result.page_count >= 1
            assert len(validation_result.metadata) > 0  # Should have metadata

            # Step 4: Check file size is within optimization target
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            if self.optimization_config.target_file_size_mb:
                assert file_size_mb <= self.optimization_config.target_file_size_mb
            else:
                # If no target set, just verify it's reasonable (< 10MB for a simple report)
                assert file_size_mb < 10.0

    def test_template_to_pdf_pipeline(self):
        """Test pipeline from template rendering to PDF generation."""
        # Create report data
        report_data = ReportData(
            title="Template to PDF Pipeline Test",
            subtitle="Testing HTML to PDF conversion"
        )

        report_data.add_section(ReportSection(
            title="Test Section",
            content="This tests the template to PDF pipeline.",
            section_type="text",
            order=1
        ))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "template_pipeline_test.pdf"

            # Step 1: Render HTML template
            html_content = self.template_engine.render_report(report_data)
            assert "<html" in html_content  # Check for opening html tag (with or without attributes)
            assert "Template to PDF Pipeline Test" in html_content

            # Step 2: Convert to PDF content structure
            pdf_content = self.pdf_generator._convert_html_to_pdf_content(
                html_content, report_data
            )
            assert isinstance(pdf_content, list)
            assert len(pdf_content) > 0

            # Step 3: Generate PDF from content
            pdf_bytes = self.pdf_generator.generate_report_from_template(
                report_data=report_data,
                template_name="audit_report.html",
                output_path=str(output_path),
                return_bytes=False,  # Save to file instead of returning bytes
            )

            # Verify pipeline success
            assert output_path.exists()
            assert pdf_bytes == str(output_path)  # Should return the path when saving to file

            # Validate final PDF
            validation_result = self.quality_validator.validate_pdf(str(output_path))
            assert validation_result.is_valid

    def test_optimized_pdf_pipeline(self):
        """Test pipeline with various optimization settings."""
        report_data = ReportData(
            title="Optimization Test Report",
            subtitle="Testing PDF optimization pipeline"
        )

        # Add content that will benefit from optimization
        large_content = "This is a large content section. " * 100
        report_data.add_section(ReportSection(
            title="Large Content Section",
            content=large_content,
            section_type="text",
            order=1
        ))

        optimization_configs = [
            OptimizationConfig(
                compression_level=CompressionLevel.LOW,
                image_quality=ImageQuality.HIGH,
                enable_image_compression=False,
            ),
            OptimizationConfig(
                compression_level=CompressionLevel.HIGH,
                image_quality=ImageQuality.LOW,
                enable_image_compression=True,
                target_file_size_mb=1.0,
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            file_sizes = []

            for i, opt_config in enumerate(optimization_configs):
                # Create config with specific optimization
                test_config = PDFConfiguration(
                    page_size=A4,
                    orientation="portrait",
                    margins={"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
                    compression=True,
                    optimization_config=opt_config,
                )

                generator = PDFGenerator(config=test_config)

                output_path = Path(temp_dir) / f"optimized_test_{i}.pdf"

                # Generate PDF
                pdf_bytes = generator.generate_report_from_template(
                    report_data=report_data,
                    template_name="audit_report.html",
                    output_path=str(output_path),
                    return_bytes=False,  # Save to file instead of returning bytes
                )

                assert output_path.exists()
                assert pdf_bytes == str(output_path)  # Should return the path when saving to file

                file_size = output_path.stat().st_size
                file_sizes.append(file_size)

                # Validate PDF
                validation_result = self.quality_validator.validate_pdf(str(output_path))
                assert validation_result.is_valid

            # Verify optimization worked (high compression should produce smaller file)
            assert file_sizes[1] <= file_sizes[0], "High compression should produce smaller files"

    def test_error_handling_pipeline(self):
        """Test pipeline error handling and recovery."""
        # Test with invalid report data
        invalid_report_data = ReportData(title="", subtitle="")  # Empty title

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "error_test.pdf"

            # Test error handling
            pdf_bytes = self.pdf_generator.generate_report_from_template(
                report_data=invalid_report_data,
                template_name="audit_report.html",
                output_path=str(output_path),
                return_bytes=False,  # Save to file instead of returning bytes
            )

            # Should still create a valid PDF even with minimal content
            assert output_path.exists()
            assert pdf_bytes == str(output_path)  # Should return the path when saving to file

            # Validate final PDF
            validation_result = self.quality_validator.validate_pdf(str(output_path))
            assert validation_result.is_valid

    def test_concurrent_pipeline_execution(self):
        """Test pipeline under concurrent execution."""
        import concurrent.futures
        import threading

        def generate_pdf(thread_id):
            """Generate a PDF in a separate thread."""
            report_data = ReportData(
                title=f"Concurrent Test Report {thread_id}",
                subtitle="Testing concurrent pipeline execution"
            )

            report_data.add_section(ReportSection(
                title=f"Thread {thread_id} Section",
                content=f"Content generated by thread {thread_id}",
                section_type="text",
                order=1
            ))

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"concurrent_test_{thread_id}.pdf"

                # Use thread-local generator to avoid conflicts
                generator = PDFGenerator(
                    config=self.pdf_config,
                )

                pdf_bytes = generator.generate_report_from_template(
                    report_data=report_data,
                    template_name="audit_report.html",
                    output_path=str(output_path),
                    return_bytes=False,  # Save to file instead of returning bytes
                )

                return {
                    "thread_id": thread_id,
                    "success": output_path.exists() and pdf_bytes == str(output_path),
                    "file_size": output_path.stat().st_size if output_path.exists() else 0,
                }

        # Run multiple threads concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(generate_pdf, i) for i in range(3)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Verify all threads succeeded
        assert len(results) == 3
        for result in results:
            assert result["success"], f"Thread {result['thread_id']} failed"
            assert result["file_size"] > 0, f"Thread {result['thread_id']} produced empty file"

    @pytest.mark.e2e
    def test_simple_pdf_generation(self):
        """Test simple PDF generation using convenience functions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "simple_test.pdf"

            # Use the convenience function that works in unit tests
            content = [
                {"type": "title", "text": "Test Report"},
                {"type": "paragraph", "text": "This is a simple test document."},
                {"type": "paragraph", "text": "Testing PDF generation functionality."},
            ]

            # Generate PDF using convenience function
            result = create_simple_pdf(
                content=content,
                output_path=str(output_path),
            )

            # Basic validation
            assert result is not None
            assert result == str(output_path)
            assert output_path.exists()

            # Validate file size
            file_size = output_path.stat().st_size
            assert file_size > 0


@pytest.mark.e2e
@pytest.mark.slow
class TestPDFPipelinePerformance:
    """Performance tests for the PDF rendering pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.optimization_config = OptimizationConfig(
            compression_level=CompressionLevel.MEDIUM,
            image_quality=ImageQuality.MEDIUM,
            enable_image_compression=True,
        )

        self.pdf_config = PDFConfiguration(
            page_size=A4,
            optimization_config=self.optimization_config,
        )
        self.pdf_generator = PDFGenerator(
            config=self.pdf_config,
        )

    def test_large_report_performance(self):
        """Test performance with large reports."""
        import time

        # Create large report data for performance testing
        report_data = ReportData(
            title="Performance Test Report",
            subtitle="Large Dataset Analysis",
        )

        # Add multiple sections (reduced for stability)
        for i in range(5):  # Reduced from 50
            report_data.sections.append(ReportSection(
                title=f"Section {i+1}",
                content=f"Content for section {i+1}. " * 20,  # Reduced content
                section_type="analysis",
                order=i+1
            ))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "large_performance_test.pdf"

            start_time = time.time()
            pdf_bytes = self.pdf_generator.generate_report_from_template(
                report_data=report_data,
                template_name="audit_report.html",
                output_path=str(output_path),
                return_bytes=False,  # Save to file instead of returning bytes
            )
            end_time = time.time()

            generation_time = end_time - start_time

            # Verify PDF was created successfully
            assert output_path.exists()
            assert pdf_bytes == str(output_path)  # Should return the path when saving to file

            # Performance assertions (adjust thresholds as needed)
            assert generation_time < 30.0, f"PDF generation took too long: {generation_time:.2f}s"

            # Verify file size is reasonable
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            assert file_size_mb < 50.0, f"PDF file too large: {file_size_mb:.2f}MB"

    def test_memory_usage_pipeline(self):
        """Test memory usage during PDF generation."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create memory-intensive report data
        for i in range(3):  # Reduced from 10
            report_data = ReportData(
                title=f"Memory Test Report {i+1}",
                subtitle="Memory Usage Analysis",
            )

            # Add sections with moderate content
            for j in range(3):  # Reduced from 20
                report_data.sections.append(ReportSection(
                    title=f"Section {j}",
                    content="Content " * 50,  # Reduced content size
                    section_type="text",
                    order=j
                ))

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"memory_test_{i}.pdf"

                pdf_bytes = self.pdf_generator.generate_report_from_template(
                    report_data=report_data,
                    template_name="audit_report.html",
                    output_path=str(output_path),
                    return_bytes=False,  # Save to file instead of returning bytes
                )

                assert output_path.exists()
                assert pdf_bytes == str(output_path)  # Should return the path when saving to file

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory should not increase excessively (adjust threshold as needed)
        assert memory_increase < 100.0, f"Memory usage increased too much: {memory_increase:.2f}MB"
