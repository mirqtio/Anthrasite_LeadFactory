"""
Report delivery service for secure audit report distribution.

This module combines Supabase storage with secure link generation to provide
a complete report delivery system for the Stripe webhook flow.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Union

from leadfactory.email.delivery import EmailDeliveryService
from leadfactory.email.secure_links import SecureLinkData, SecureLinkGenerator
from leadfactory.storage.supabase_storage import SupabaseStorage

logger = logging.getLogger(__name__)


class ReportDeliveryService:
    """
    Service for handling complete report delivery workflow.

    Integrates PDF upload to Supabase, secure URL generation,
    and email delivery for audit reports.
    """

    def __init__(self, storage_bucket: str = "reports", link_expiry_hours: int = 72):
        """
        Initialize the report delivery service.

        Args:
            storage_bucket: Supabase storage bucket for reports
            link_expiry_hours: Default expiry time for secure links in hours
        """
        self.storage = SupabaseStorage(bucket_name=storage_bucket)
        self.link_generator = SecureLinkGenerator()
        self.email_service = EmailDeliveryService()
        self.default_expiry_hours = link_expiry_hours

        logger.info(f"Report delivery service initialized (bucket: {storage_bucket})")

    def upload_and_deliver_report(
        self,
        pdf_path: Union[str, Path],
        report_id: str,
        user_id: str,
        user_email: str,
        purchase_id: str,
        business_name: str,
        expiry_hours: Optional[int] = None,
    ) -> Dict[str, any]:
        """
        Complete workflow: upload PDF, generate secure link, and send email.

        Args:
            pdf_path: Local path to the PDF report
            report_id: Unique identifier for the report
            user_id: User who purchased the report
            user_email: Email address for delivery
            purchase_id: Stripe purchase/payment intent ID
            business_name: Name of the business in the report
            expiry_hours: Custom expiry time (uses default if not provided)

        Returns:
            Dict containing delivery status and metadata

        Raises:
            Exception: If any step of the delivery process fails
        """
        expiry_hours = expiry_hours or self.default_expiry_hours

        try:
            # Step 1: Upload PDF to Supabase
            logger.info(f"Uploading report {report_id} for user {user_id}")
            upload_result = self.storage.upload_pdf_report(
                pdf_path=pdf_path,
                report_id=report_id,
                user_id=user_id,
                purchase_id=purchase_id,
            )

            storage_path = upload_result["storage_path"]

            # Step 2: Generate secure access link
            logger.info(f"Generating secure link for report {report_id}")
            secure_link_data = self._create_secure_link_data(
                report_id=report_id,
                user_id=user_id,
                purchase_id=purchase_id,
                storage_path=storage_path,
                expiry_hours=expiry_hours,
            )

            secure_token = self.link_generator.generate_secure_link(
                data=secure_link_data,
                expiry_days=expiry_hours / 24,  # Convert hours to days
            )

            # Step 3: Generate Supabase signed URL
            supabase_url_data = self.storage.generate_secure_report_url(
                storage_path=storage_path, expires_in_hours=expiry_hours
            )

            # Step 4: Send delivery email
            logger.info(f"Sending delivery email to {user_email}")
            email_result = self._send_delivery_email(
                user_email=user_email,
                business_name=business_name,
                secure_token=secure_token,
                signed_url=supabase_url_data["signed_url"],
                expires_at=supabase_url_data["expires_at"],
            )

            # Compile delivery result
            delivery_result = {
                "status": "delivered",
                "report_id": report_id,
                "user_id": user_id,
                "purchase_id": purchase_id,
                "storage_path": storage_path,
                "secure_token": secure_token,
                "signed_url": supabase_url_data["signed_url"],
                "expires_at": supabase_url_data["expires_at"],
                "email_sent": email_result.get("success", False),
                "email_id": email_result.get("email_id"),
                "delivered_at": datetime.utcnow().isoformat(),
                "upload_metadata": upload_result,
            }

            logger.info(f"Successfully delivered report {report_id} to {user_email}")
            return delivery_result

        except Exception as e:
            logger.error(f"Failed to deliver report {report_id}: {e}")
            raise

    def _create_secure_link_data(
        self,
        report_id: str,
        user_id: str,
        purchase_id: str,
        storage_path: str,
        expiry_hours: int,
    ) -> SecureLinkData:
        """
        Create secure link data structure.

        Args:
            report_id: Report identifier
            user_id: User identifier
            purchase_id: Purchase identifier
            storage_path: Path in Supabase storage
            expiry_hours: Expiry time in hours

        Returns:
            SecureLinkData instance
        """
        expires_at = int(
            (datetime.utcnow() + timedelta(hours=expiry_hours)).timestamp()
        )

        return SecureLinkData(
            report_id=report_id,
            user_id=user_id,
            purchase_id=purchase_id,
            expires_at=expires_at,
            access_type="download",
            metadata={
                "storage_path": storage_path,
                "delivery_method": "supabase_storage",
                "expiry_hours": expiry_hours,
            },
        )

    def _send_delivery_email(
        self,
        user_email: str,
        business_name: str,
        secure_token: str,
        signed_url: str,
        expires_at: str,
    ) -> Dict[str, any]:
        """
        Send report delivery email to user.

        Args:
            user_email: Recipient email address
            business_name: Business name for the report
            secure_token: JWT token for secure access
            signed_url: Direct Supabase signed URL
            expires_at: Expiration timestamp

        Returns:
            Email sending result
        """
        try:
            # Parse expiration for user-friendly display
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            expires_friendly = expires_dt.strftime("%B %d, %Y at %I:%M %p UTC")

            # Prepare email content
            subject = f"Your {business_name} Audit Report is Ready"

            # For now, use the direct signed URL
            # In production, you might want to route through your app with the secure token
            download_link = signed_url

            email_content = {
                "business_name": business_name,
                "download_link": download_link,
                "expires_at": expires_friendly,
                "secure_token": secure_token,  # Could be used for additional verification
            }

            # Send email using the email delivery service
            result = self.email_service.send_email(
                to_email=user_email,
                subject=subject,
                template_name="report_delivery",
                template_data=email_content,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send delivery email to {user_email}: {e}")
            return {"success": False, "error": str(e)}

    def validate_and_get_report_access(self, secure_token: str) -> Dict[str, any]:
        """
        Validate a secure token and return report access information.

        Args:
            secure_token: JWT token from secure link

        Returns:
            Dict containing validation result and access info

        Raises:
            Exception: If token is invalid or expired
        """
        try:
            # Validate the secure link token
            link_data = self.link_generator.validate_secure_link(secure_token)

            # Get storage path from metadata
            storage_path = link_data.metadata.get("storage_path")
            if not storage_path:
                raise ValueError("Storage path not found in token metadata")

            # Generate a fresh signed URL for access
            # This provides additional security by generating a new URL each time
            fresh_url_data = self.storage.generate_secure_report_url(
                storage_path=storage_path,
                expires_in_hours=1,  # Short-lived URL for immediate download
            )

            return {
                "valid": True,
                "report_id": link_data.report_id,
                "user_id": link_data.user_id,
                "purchase_id": link_data.purchase_id,
                "access_type": link_data.access_type,
                "storage_path": storage_path,
                "download_url": fresh_url_data["signed_url"],
                "download_expires_at": fresh_url_data["expires_at"],
                "original_expires_at": link_data.expires_at,
            }

        except Exception as e:
            logger.error(f"Failed to validate secure token: {e}")
            return {"valid": False, "error": str(e)}

    def get_delivery_status(self, report_id: str, user_id: str) -> Dict[str, any]:
        """
        Get delivery status for a specific report.

        Args:
            report_id: Report identifier
            user_id: User identifier

        Returns:
            Dict containing delivery status information
        """
        try:
            # This would typically query a database for delivery records
            # For now, we'll check if the file exists in storage

            # Look for files matching the report pattern
            files = self.storage.list_files(prefix=f"reports/{user_id}/")

            matching_files = [f for f in files if report_id in f.get("name", "")]

            if matching_files:
                return {
                    "status": "delivered",
                    "report_id": report_id,
                    "user_id": user_id,
                    "files_found": len(matching_files),
                    "latest_file": matching_files[0] if matching_files else None,
                }
            else:
                return {
                    "status": "not_found",
                    "report_id": report_id,
                    "user_id": user_id,
                    "files_found": 0,
                }

        except Exception as e:
            logger.error(f"Failed to get delivery status for {report_id}: {e}")
            return {"status": "error", "error": str(e)}

    def cleanup_expired_reports(self, days_old: int = 30) -> Dict[str, any]:
        """
        Clean up expired reports from storage.

        Args:
            days_old: Delete reports older than this many days

        Returns:
            Dict containing cleanup results
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            # List all files in the reports bucket
            all_files = self.storage.list_files(prefix="reports/")

            deleted_count = 0
            errors = []

            for file_info in all_files:
                try:
                    # Check file creation date
                    created_at = file_info.get("created_at")
                    if created_at:
                        # Handle both ISO format with and without 'Z' suffix
                        if created_at.endswith("Z"):
                            file_date = datetime.fromisoformat(
                                created_at.replace("Z", "+00:00")
                            )
                        else:
                            file_date = datetime.fromisoformat(created_at)

                        if file_date.replace(tzinfo=None) < cutoff_date:
                            # Delete the file
                            file_path = file_info.get("name")
                            if file_path:
                                self.storage.delete_file(file_path)
                                deleted_count += 1
                                logger.info(f"Deleted expired report: {file_path}")

                except Exception as e:
                    errors.append(
                        f"Error processing {file_info.get('name', 'unknown')}: {e}"
                    )

            return {
                "status": "completed",
                "deleted_count": deleted_count,
                "errors": errors,
                "cutoff_date": cutoff_date.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to cleanup expired reports: {e}")
            return {"status": "error", "error": str(e)}
