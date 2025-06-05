"""
Local PDF Delivery Service

This module provides local PDF delivery options that bypass cloud storage,
including email attachments and local HTTP serving.
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Union
from urllib.parse import urljoin

from leadfactory.config.settings import (
    LOCAL_PDF_BASE_URL,
    LOCAL_PDF_STORAGE_PATH,
    PDF_EMAIL_MAX_SIZE_MB,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class LocalPDFDeliveryService:
    """
    Service for handling local PDF delivery without cloud storage.
    
    Supports two modes:
    1. Email attachment - Attach PDF directly to delivery email
    2. Local HTTP serving - Serve PDFs via local web server
    """
    
    def __init__(
        self,
        storage_path: str = LOCAL_PDF_STORAGE_PATH,
        base_url: str = LOCAL_PDF_BASE_URL,
        max_email_size_mb: int = PDF_EMAIL_MAX_SIZE_MB,
    ):
        """
        Initialize the local PDF delivery service.
        
        Args:
            storage_path: Local directory to store PDF files
            base_url: Base URL for local HTTP serving
            max_email_size_mb: Maximum file size for email attachments (MB)
        """
        self.storage_path = Path(storage_path)
        self.base_url = base_url.rstrip('/')
        self.max_email_size_bytes = max_email_size_mb * 1024 * 1024
        
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Local PDF delivery service initialized: {self.storage_path}")
    
    def store_pdf_locally(
        self, 
        pdf_path: Union[str, Path], 
        report_id: str,
        user_id: str
    ) -> Dict[str, str]:
        """
        Store a PDF file in the local storage directory.
        
        Args:
            pdf_path: Path to the source PDF file
            report_id: Unique identifier for the report
            user_id: User ID for organizing files
            
        Returns:
            Dict containing storage information
        """
        try:
            # Create user-specific directory
            user_dir = self.storage_path / user_id
            user_dir.mkdir(exist_ok=True)
            
            # Generate filename with timestamp for uniqueness
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_id}_{timestamp}.pdf"
            local_path = user_dir / filename
            
            # Copy PDF to local storage
            shutil.copy2(pdf_path, local_path)
            
            # Get file size
            file_size = local_path.stat().st_size
            
            logger.info(f"PDF stored locally: {local_path} ({file_size} bytes)")
            
            return {
                "local_path": str(local_path),
                "relative_path": f"{user_id}/{filename}",
                "file_size": file_size,
                "filename": filename,
                "stored_at": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to store PDF locally: {e}")
            raise
    
    def generate_local_url(self, relative_path: str, expiry_hours: int = 720) -> Dict[str, str]:
        """
        Generate a local HTTP URL for accessing the PDF.
        
        Args:
            relative_path: Relative path within the storage directory
            expiry_hours: How long the URL should be valid (hours)
            
        Returns:
            Dict containing URL and expiry information
        """
        try:
            # Generate download URL
            download_url = urljoin(f"{self.base_url}/", relative_path)
            
            # Calculate expiry time
            expires_at = datetime.now() + timedelta(hours=expiry_hours)
            
            logger.info(f"Generated local URL: {download_url}")
            
            return {
                "download_url": download_url,
                "expires_at": expires_at.isoformat(),
                "expiry_hours": expiry_hours,
                "access_method": "local_http",
            }
            
        except Exception as e:
            logger.error(f"Failed to generate local URL: {e}")
            raise
    
    def prepare_email_attachment(
        self, 
        pdf_path: Union[str, Path],
        report_id: str
    ) -> Dict[str, Union[str, bytes, bool]]:
        """
        Prepare PDF for email attachment, including size validation.
        
        Args:
            pdf_path: Path to the PDF file
            report_id: Report identifier for filename
            
        Returns:
            Dict containing attachment data or error information
        """
        try:
            pdf_path = Path(pdf_path)
            
            # Check if file exists
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Get file size
            file_size = pdf_path.stat().st_size
            
            # Check size limit for email attachment
            if file_size > self.max_email_size_bytes:
                logger.warning(
                    f"PDF too large for email attachment: {file_size} bytes "
                    f"(max: {self.max_email_size_bytes} bytes)"
                )
                return {
                    "attachment_ready": False,
                    "file_size": file_size,
                    "max_size": self.max_email_size_bytes,
                    "reason": "file_too_large",
                    "fallback_required": True,
                }
            
            # Read PDF content for attachment
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()
            
            # Generate attachment filename
            timestamp = datetime.now().strftime("%Y%m%d")
            attachment_filename = f"audit_report_{report_id}_{timestamp}.pdf"
            
            logger.info(f"PDF prepared for email attachment: {file_size} bytes")
            
            return {
                "attachment_ready": True,
                "pdf_content": pdf_content,
                "filename": attachment_filename,
                "file_size": file_size,
                "content_type": "application/pdf",
                "fallback_required": False,
            }
            
        except Exception as e:
            logger.error(f"Failed to prepare email attachment: {e}")
            return {
                "attachment_ready": False,
                "error": str(e),
                "fallback_required": True,
            }
    
    def deliver_via_email_attachment(
        self,
        pdf_path: Union[str, Path],
        report_id: str,
        user_email: str,
        business_name: str,
        email_service=None
    ) -> Dict[str, any]:
        """
        Deliver PDF via email attachment.
        
        Args:
            pdf_path: Path to the PDF file
            report_id: Report identifier
            user_email: Recipient email address
            business_name: Name of the business in the report
            email_service: Email service instance for sending
            
        Returns:
            Dict containing delivery status and information
        """
        try:
            # Prepare attachment
            attachment_data = self.prepare_email_attachment(pdf_path, report_id)
            
            if not attachment_data.get("attachment_ready", False):
                return {
                    "delivery_method": "email_attachment",
                    "success": False,
                    "reason": attachment_data.get("reason", "preparation_failed"),
                    "fallback_required": attachment_data.get("fallback_required", True),
                    "error": attachment_data.get("error"),
                }
            
            # Prepare email content
            email_data = {
                "to_email": user_email,
                "subject": f"Your Website Audit Report - {business_name}",
                "content": self._build_attachment_email_content(business_name, report_id),
                "attachments": [
                    {
                        "content": attachment_data["pdf_content"],
                        "filename": attachment_data["filename"],
                        "content_type": attachment_data["content_type"],
                    }
                ],
            }
            
            # Send email with attachment
            if email_service:
                send_result = email_service.send_email(**email_data)
                success = send_result.get("success", False)
            else:
                logger.warning("No email service provided, simulating send")
                success = True
                send_result = {"message_id": f"local_{report_id}"}
            
            if success:
                logger.info(f"PDF delivered via email attachment to {user_email}")
                return {
                    "delivery_method": "email_attachment",
                    "success": True,
                    "email_sent": True,
                    "attachment_size": attachment_data["file_size"],
                    "message_id": send_result.get("message_id"),
                    "delivered_at": datetime.now().isoformat(),
                }
            else:
                return {
                    "delivery_method": "email_attachment",
                    "success": False,
                    "reason": "email_send_failed",
                    "fallback_required": True,
                    "error": send_result.get("error"),
                }
                
        except Exception as e:
            logger.error(f"Failed to deliver PDF via email attachment: {e}")
            return {
                "delivery_method": "email_attachment",
                "success": False,
                "reason": "delivery_failed",
                "fallback_required": True,
                "error": str(e),
            }
    
    def deliver_via_local_http(
        self,
        pdf_path: Union[str, Path],
        report_id: str,
        user_id: str,
        user_email: str,
        business_name: str,
        expiry_hours: int = 720,
        email_service=None
    ) -> Dict[str, any]:
        """
        Deliver PDF via local HTTP serving with download link.
        
        Args:
            pdf_path: Path to the PDF file
            report_id: Report identifier
            user_id: User identifier for file organization
            user_email: User email for notification
            business_name: Name of the business in the report
            expiry_hours: How long the download link should be valid
            email_service: Email service for sending download link
            
        Returns:
            Dict containing delivery status and information
        """
        try:
            # Store PDF locally
            storage_result = self.store_pdf_locally(pdf_path, report_id, user_id)
            
            # Generate download URL
            url_result = self.generate_local_url(
                storage_result["relative_path"], 
                expiry_hours
            )
            
            # Prepare notification email
            email_data = {
                "to_email": user_email,
                "subject": f"Your Website Audit Report - {business_name}",
                "content": self._build_download_email_content(
                    business_name, 
                    report_id, 
                    url_result["download_url"],
                    url_result["expires_at"]
                ),
            }
            
            # Send notification email
            if email_service:
                send_result = email_service.send_email(**email_data)
                email_sent = send_result.get("success", False)
                message_id = send_result.get("message_id")
            else:
                logger.warning("No email service provided, simulating send")
                email_sent = True
                message_id = f"local_{report_id}"
            
            logger.info(f"PDF delivered via local HTTP: {url_result['download_url']}")
            
            return {
                "delivery_method": "local_http",
                "success": True,
                "download_url": url_result["download_url"],
                "local_path": storage_result["local_path"],
                "file_size": storage_result["file_size"],
                "expires_at": url_result["expires_at"],
                "email_sent": email_sent,
                "message_id": message_id,
                "delivered_at": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to deliver PDF via local HTTP: {e}")
            return {
                "delivery_method": "local_http",
                "success": False,
                "reason": "delivery_failed",
                "error": str(e),
            }
    
    def _build_attachment_email_content(self, business_name: str, report_id: str) -> str:
        """Build email content for attachment delivery."""
        return f"""
Dear Customer,

Thank you for your purchase! Please find your website audit report for {business_name} attached to this email.

Report Details:
- Report ID: {report_id}
- Business: {business_name}
- Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

The attached PDF contains a comprehensive analysis of your website including:
- Performance metrics and optimization recommendations
- SEO analysis and improvement suggestions
- Technical review and actionable insights

If you have any questions about your report, please don't hesitate to contact our support team.

Best regards,
Anthrasite Digital Team
        """.strip()
    
    def _build_download_email_content(
        self, 
        business_name: str, 
        report_id: str, 
        download_url: str,
        expires_at: str
    ) -> str:
        """Build email content for download link delivery."""
        expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        expiry_formatted = expiry_date.strftime('%B %d, %Y at %I:%M %p')
        
        return f"""
Dear Customer,

Thank you for your purchase! Your website audit report for {business_name} is ready for download.

Report Details:
- Report ID: {report_id}
- Business: {business_name}
- Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

Download Link: {download_url}

Important: This download link will expire on {expiry_formatted}. Please download your report before this date.

Your PDF report contains a comprehensive analysis of your website including:
- Performance metrics and optimization recommendations
- SEO analysis and improvement suggestions
- Technical review and actionable insights

If you have any questions about your report or trouble accessing the download link, please contact our support team.

Best regards,
Anthrasite Digital Team
        """.strip()
    
    def cleanup_expired_files(self, max_age_days: int = 60) -> Dict[str, int]:
        """
        Clean up expired PDF files from local storage.
        
        Args:
            max_age_days: Maximum age of files to keep (days)
            
        Returns:
            Dict with cleanup statistics
        """
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
            
            files_removed = 0
            bytes_freed = 0
            
            for pdf_file in self.storage_path.rglob("*.pdf"):
                if pdf_file.stat().st_mtime < cutoff_time:
                    file_size = pdf_file.stat().st_size
                    pdf_file.unlink()
                    files_removed += 1
                    bytes_freed += file_size
                    logger.debug(f"Removed expired PDF: {pdf_file}")
            
            # Remove empty directories
            for user_dir in self.storage_path.iterdir():
                if user_dir.is_dir() and not any(user_dir.iterdir()):
                    user_dir.rmdir()
                    logger.debug(f"Removed empty directory: {user_dir}")
            
            logger.info(
                f"Cleanup completed: {files_removed} files removed, "
                f"{bytes_freed / (1024*1024):.2f} MB freed"
            )
            
            return {
                "files_removed": files_removed,
                "bytes_freed": bytes_freed,
                "max_age_days": max_age_days,
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired files: {e}")
            return {"files_removed": 0, "bytes_freed": 0, "error": str(e)}