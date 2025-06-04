"""
PDF Quality Validation and Integrity Service

This service provides comprehensive PDF quality validation, integrity checks,
file size optimization, and automated testing for PDF structure, readability,
and security compliance.

Features:
- PDF structure validation
- Content integrity verification
- File size optimization analysis
- Security compliance checking
- Readability assessment
- Metadata validation
- Error detection and reporting
"""

import hashlib
import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import PyPDF2

    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationCategory(Enum):
    """Categories of validation checks."""

    STRUCTURE = "structure"
    CONTENT = "content"
    SECURITY = "security"
    OPTIMIZATION = "optimization"
    METADATA = "metadata"
    ACCESSIBILITY = "accessibility"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in a PDF."""

    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    details: Optional[str] = None
    page_number: Optional[int] = None
    location: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class PDFQualityReport:
    """Comprehensive quality report for a PDF."""

    file_path: Optional[str]
    file_size: int
    page_count: int
    validation_timestamp: datetime
    overall_score: float  # 0-100
    issues: List[ValidationIssue]
    metadata: Dict[str, Any]
    security_info: Dict[str, Any]
    optimization_suggestions: List[str]
    is_valid: bool

    def get_issues_by_severity(
        self, severity: ValidationSeverity
    ) -> List[ValidationIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]

    def get_issues_by_category(
        self, category: ValidationCategory
    ) -> List[ValidationIssue]:
        """Get all issues of a specific category."""
        return [issue for issue in self.issues if issue.category == category]

    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(
            issue.severity == ValidationSeverity.CRITICAL for issue in self.issues
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the validation results."""
        severity_counts = {}
        category_counts = {}

        for issue in self.issues:
            severity_counts[issue.severity.value] = (
                severity_counts.get(issue.severity.value, 0) + 1
            )
            category_counts[issue.category.value] = (
                category_counts.get(issue.category.value, 0) + 1
            )

        return {
            "overall_score": self.overall_score,
            "is_valid": self.is_valid,
            "total_issues": len(self.issues),
            "critical_issues": len(
                self.get_issues_by_severity(ValidationSeverity.CRITICAL)
            ),
            "error_issues": len(self.get_issues_by_severity(ValidationSeverity.ERROR)),
            "warning_issues": len(
                self.get_issues_by_severity(ValidationSeverity.WARNING)
            ),
            "info_issues": len(self.get_issues_by_severity(ValidationSeverity.INFO)),
            "severity_breakdown": severity_counts,
            "category_breakdown": category_counts,
            "file_size_mb": round(self.file_size / (1024 * 1024), 2),
            "page_count": self.page_count,
        }


class PDFQualityValidator:
    """
    Comprehensive PDF quality validation service.

    Provides validation for PDF structure, content, security, and optimization.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the PDF quality validator."""
        self.config = config or {}
        self.max_file_size_mb = self.config.get("max_file_size_mb", 50)
        self.min_quality_score = self.config.get("min_quality_score", 80)
        self.check_security = self.config.get("check_security", True)
        self.check_optimization = self.config.get("check_optimization", True)
        self.check_accessibility = self.config.get("check_accessibility", False)

        logger.info("PDF Quality Validator initialized")

    def validate_pdf(self, pdf_data: Union[bytes, str, Path]) -> PDFQualityReport:
        """
        Perform comprehensive validation of a PDF.

        Args:
            pdf_data: PDF data as bytes, file path as string, or Path object

        Returns:
            PDFQualityReport with validation results
        """
        try:
            # Prepare PDF data
            if isinstance(pdf_data, (str, Path)):
                file_path = str(pdf_data)
                with open(file_path, "rb") as f:
                    pdf_bytes = f.read()
            else:
                file_path = None
                pdf_bytes = pdf_data

            # Initialize report
            issues = []
            metadata = {}
            security_info = {}
            optimization_suggestions = []

            # Basic file validation
            file_size = len(pdf_bytes)
            if file_size == 0:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.STRUCTURE,
                        severity=ValidationSeverity.CRITICAL,
                        message="PDF file is empty",
                        suggestion="Ensure PDF generation completed successfully",
                    )
                )
                return self._create_failed_report(file_path, issues)

            # Check file size
            file_size_mb = file_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.OPTIMIZATION,
                        severity=ValidationSeverity.WARNING,
                        message=f"File size ({file_size_mb:.2f}MB) exceeds recommended limit ({self.max_file_size_mb}MB)",
                        suggestion="Consider optimizing images or reducing content",
                    )
                )

            # PDF structure validation
            page_count = 0
            if PYPDF2_AVAILABLE:
                try:
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                    page_count = len(pdf_reader.pages)

                    # Extract metadata
                    if pdf_reader.metadata:
                        metadata = {
                            "title": pdf_reader.metadata.get("/Title", ""),
                            "author": pdf_reader.metadata.get("/Author", ""),
                            "subject": pdf_reader.metadata.get("/Subject", ""),
                            "creator": pdf_reader.metadata.get("/Creator", ""),
                            "producer": pdf_reader.metadata.get("/Producer", ""),
                            "creation_date": pdf_reader.metadata.get(
                                "/CreationDate", ""
                            ),
                            "modification_date": pdf_reader.metadata.get(
                                "/ModDate", ""
                            ),
                        }

                    # Security information
                    if hasattr(pdf_reader, "is_encrypted"):
                        security_info["encrypted"] = pdf_reader.is_encrypted

                    # Validate each page
                    for i, page in enumerate(pdf_reader.pages):
                        page_issues = self._validate_page(page, i + 1)
                        issues.extend(page_issues)

                except Exception as e:
                    issues.append(
                        ValidationIssue(
                            category=ValidationCategory.STRUCTURE,
                            severity=ValidationSeverity.ERROR,
                            message=f"Failed to read PDF structure: {str(e)}",
                            suggestion="Check if PDF is corrupted or uses unsupported features",
                        )
                    )
            else:
                # Basic validation without PyPDF2
                if not pdf_bytes.startswith(b"%PDF-"):
                    issues.append(
                        ValidationIssue(
                            category=ValidationCategory.STRUCTURE,
                            severity=ValidationSeverity.CRITICAL,
                            message="Invalid PDF header",
                            suggestion="Ensure file is a valid PDF",
                        )
                    )

                # Estimate page count from content
                page_count = pdf_bytes.count(b"/Type /Page")

            # Content validation
            content_issues = self._validate_content(pdf_bytes)
            issues.extend(content_issues)

            # Security validation
            if self.check_security:
                security_issues = self._validate_security(pdf_bytes, security_info)
                issues.extend(security_issues)

            # Optimization validation
            if self.check_optimization:
                optimization_issues, suggestions = self._validate_optimization(
                    pdf_bytes, file_size
                )
                issues.extend(optimization_issues)
                optimization_suggestions.extend(suggestions)

            # Accessibility validation
            if self.check_accessibility:
                accessibility_issues = self._validate_accessibility(pdf_bytes)
                issues.extend(accessibility_issues)

            # Calculate overall score
            overall_score = self._calculate_quality_score(issues, file_size, page_count)

            # Determine if PDF is valid
            is_valid = overall_score >= self.min_quality_score and not any(
                issue.severity == ValidationSeverity.CRITICAL for issue in issues
            )

            return PDFQualityReport(
                file_path=file_path,
                file_size=file_size,
                page_count=page_count,
                validation_timestamp=datetime.now(),
                overall_score=overall_score,
                issues=issues,
                metadata=metadata,
                security_info=security_info,
                optimization_suggestions=optimization_suggestions,
                is_valid=is_valid,
            )

        except Exception as e:
            logger.error(f"PDF validation failed: {str(e)}")
            issues = [
                ValidationIssue(
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Validation failed: {str(e)}",
                    suggestion="Check PDF file integrity and format",
                )
            ]
            return self._create_failed_report(
                file_path if "file_path" in locals() else None, issues
            )

    def _validate_page(self, page, page_number: int) -> List[ValidationIssue]:
        """Validate a single PDF page."""
        issues = []

        try:
            # Check if page has content
            if hasattr(page, "extract_text"):
                text = page.extract_text()
                if not text or len(text.strip()) < 10:
                    issues.append(
                        ValidationIssue(
                            category=ValidationCategory.CONTENT,
                            severity=ValidationSeverity.WARNING,
                            message=f"Page {page_number} appears to have minimal text content",
                            page_number=page_number,
                            suggestion="Verify page content is correctly generated",
                        )
                    )

            # Check page dimensions
            if hasattr(page, "mediabox"):
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)

                if width <= 0 or height <= 0:
                    issues.append(
                        ValidationIssue(
                            category=ValidationCategory.STRUCTURE,
                            severity=ValidationSeverity.ERROR,
                            message=f"Page {page_number} has invalid dimensions",
                            page_number=page_number,
                            details=f"Width: {width}, Height: {height}",
                        )
                    )

                # Check for extremely large pages
                if width > 2000 or height > 2000:
                    issues.append(
                        ValidationIssue(
                            category=ValidationCategory.OPTIMIZATION,
                            severity=ValidationSeverity.WARNING,
                            message=f"Page {page_number} has unusually large dimensions",
                            page_number=page_number,
                            details=f"Width: {width}, Height: {height}",
                            suggestion="Consider optimizing page size",
                        )
                    )

        except Exception as e:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Failed to validate page {page_number}: {str(e)}",
                    page_number=page_number,
                )
            )

        return issues

    def _validate_content(self, pdf_bytes: bytes) -> List[ValidationIssue]:
        """Validate PDF content."""
        issues = []

        # Check for common PDF content markers
        content_markers = [b"/Contents", b"/Font", b"/XObject"]
        missing_markers = []

        for marker in content_markers:
            if marker not in pdf_bytes:
                missing_markers.append(marker.decode("utf-8"))

        if missing_markers:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONTENT,
                    severity=ValidationSeverity.WARNING,
                    message="PDF may be missing some content elements",
                    details=f"Missing markers: {', '.join(missing_markers)}",
                    suggestion="Verify all content was properly generated",
                )
            )

        # Check for embedded fonts
        if b"/FontDescriptor" not in pdf_bytes:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.CONTENT,
                    severity=ValidationSeverity.INFO,
                    message="PDF may not have embedded fonts",
                    suggestion="Consider embedding fonts for better compatibility",
                )
            )

        return issues

    def _validate_security(
        self, pdf_bytes: bytes, security_info: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate PDF security features."""
        issues = []

        # Check for encryption
        if not security_info.get("encrypted", False):
            if self.config.get("require_encryption", False):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.SECURITY,
                        severity=ValidationSeverity.WARNING,
                        message="PDF is not encrypted",
                        suggestion="Consider adding encryption for sensitive documents",
                    )
                )

        # Check for digital signatures
        if b"/Sig" not in pdf_bytes:
            if self.config.get("require_signatures", False):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.SECURITY,
                        severity=ValidationSeverity.INFO,
                        message="PDF is not digitally signed",
                        suggestion="Consider adding digital signatures for document integrity",
                    )
                )

        return issues

    def _validate_optimization(
        self, pdf_bytes: bytes, file_size: int
    ) -> Tuple[List[ValidationIssue], List[str]]:
        """Validate PDF optimization."""
        issues = []
        suggestions = []

        # Check compression
        if b"/Filter" not in pdf_bytes:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.OPTIMIZATION,
                    severity=ValidationSeverity.WARNING,
                    message="PDF may not be using compression",
                    suggestion="Enable compression to reduce file size",
                )
            )
            suggestions.append("Enable PDF compression")

        # Check for large images
        image_count = pdf_bytes.count(b"/Subtype /Image")
        if image_count > 10:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.OPTIMIZATION,
                    severity=ValidationSeverity.INFO,
                    message=f"PDF contains {image_count} images",
                    suggestion="Consider optimizing images to reduce file size",
                )
            )
            suggestions.append("Optimize embedded images")

        # Check file size efficiency
        content_ratio = len([b for b in pdf_bytes if b != 0]) / len(pdf_bytes)
        if content_ratio < 0.5:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.OPTIMIZATION,
                    severity=ValidationSeverity.INFO,
                    message="PDF may have inefficient space usage",
                    suggestion="Consider optimizing PDF structure",
                )
            )
            suggestions.append("Optimize PDF structure")

        return issues, suggestions

    def _validate_accessibility(self, pdf_bytes: bytes) -> List[ValidationIssue]:
        """Validate PDF accessibility features."""
        issues = []

        # Check for tagged PDF
        if b"/StructTreeRoot" not in pdf_bytes:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.ACCESSIBILITY,
                    severity=ValidationSeverity.WARNING,
                    message="PDF is not tagged for accessibility",
                    suggestion="Add structure tags for screen reader compatibility",
                )
            )

        # Check for alt text on images
        if b"/Alt" not in pdf_bytes and b"/Subtype /Image" in pdf_bytes:
            issues.append(
                ValidationIssue(
                    category=ValidationCategory.ACCESSIBILITY,
                    severity=ValidationSeverity.WARNING,
                    message="Images may be missing alternative text",
                    suggestion="Add alt text to images for accessibility",
                )
            )

        return issues

    def _calculate_quality_score(
        self, issues: List[ValidationIssue], file_size: int, page_count: int
    ) -> float:
        """Calculate overall quality score (0-100)."""
        base_score = 100.0

        # Deduct points for issues
        for issue in issues:
            if issue.severity == ValidationSeverity.CRITICAL:
                base_score -= 25
            elif issue.severity == ValidationSeverity.ERROR:
                base_score -= 15
            elif issue.severity == ValidationSeverity.WARNING:
                base_score -= 5
            elif issue.severity == ValidationSeverity.INFO:
                base_score -= 1

        # Bonus for good practices
        if file_size < 1024 * 1024:  # Less than 1MB
            base_score += 5

        if page_count > 0:
            base_score += 5

        return max(0.0, min(100.0, base_score))

    def _create_failed_report(
        self, file_path: Optional[str], issues: List[ValidationIssue]
    ) -> PDFQualityReport:
        """Create a report for a failed validation."""
        return PDFQualityReport(
            file_path=file_path,
            file_size=0,
            page_count=0,
            validation_timestamp=datetime.now(),
            overall_score=0.0,
            issues=issues,
            metadata={},
            security_info={},
            optimization_suggestions=[],
            is_valid=False,
        )

    def validate_pdf_integrity(self, pdf_data: bytes) -> bool:
        """
        Quick integrity check for PDF data.

        Args:
            pdf_data: PDF data as bytes

        Returns:
            True if PDF appears to have basic integrity
        """
        try:
            # Check PDF header
            if not pdf_data.startswith(b"%PDF-"):
                return False

            # Check for EOF marker
            if b"%%EOF" not in pdf_data[-1024:]:
                return False

            # Check for basic structure
            required_elements = [b"/Type", b"/Root"]
            for element in required_elements:
                if element not in pdf_data:
                    return False

            return True

        except Exception:
            return False

    def get_pdf_checksum(self, pdf_data: bytes) -> str:
        """
        Generate a checksum for PDF data.

        Args:
            pdf_data: PDF data as bytes

        Returns:
            SHA-256 checksum as hex string
        """
        return hashlib.sha256(pdf_data).hexdigest()

    def compare_pdfs(self, pdf1_data: bytes, pdf2_data: bytes) -> Dict[str, Any]:
        """
        Compare two PDFs for differences.

        Args:
            pdf1_data: First PDF data
            pdf2_data: Second PDF data

        Returns:
            Comparison results
        """
        comparison = {
            "identical": False,
            "size_difference": abs(len(pdf1_data) - len(pdf2_data)),
            "checksum_match": False,
            "structure_differences": [],
        }

        # Checksum comparison
        checksum1 = self.get_pdf_checksum(pdf1_data)
        checksum2 = self.get_pdf_checksum(pdf2_data)
        comparison["checksum_match"] = checksum1 == checksum2
        comparison["identical"] = comparison["checksum_match"]

        if not comparison["identical"]:
            # Basic structure comparison
            if len(pdf1_data) != len(pdf2_data):
                comparison["structure_differences"].append("Different file sizes")

            # Check page count differences
            page_count1 = pdf1_data.count(b"/Type /Page")
            page_count2 = pdf2_data.count(b"/Type /Page")
            if page_count1 != page_count2:
                comparison["structure_differences"].append(
                    f"Different page counts: {page_count1} vs {page_count2}"
                )

        return comparison


def validate_pdf_file(
    file_path: Union[str, Path], config: Optional[Dict[str, Any]] = None
) -> PDFQualityReport:
    """
    Convenience function to validate a PDF file.

    Args:
        file_path: Path to PDF file
        config: Optional validation configuration

    Returns:
        PDFQualityReport with validation results
    """
    validator = PDFQualityValidator(config)
    return validator.validate_pdf(file_path)


def validate_pdf_bytes(
    pdf_data: bytes, config: Optional[Dict[str, Any]] = None
) -> PDFQualityReport:
    """
    Convenience function to validate PDF data.

    Args:
        pdf_data: PDF data as bytes
        config: Optional validation configuration

    Returns:
        PDFQualityReport with validation results
    """
    validator = PDFQualityValidator(config)
    return validator.validate_pdf(pdf_data)


def quick_pdf_check(pdf_data: bytes) -> bool:
    """
    Quick integrity check for PDF data.

    Args:
        pdf_data: PDF data as bytes

    Returns:
        True if PDF appears valid
    """
    validator = PDFQualityValidator()
    return validator.validate_pdf_integrity(pdf_data)
