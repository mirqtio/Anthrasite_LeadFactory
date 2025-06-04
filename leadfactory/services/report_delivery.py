"""
Report delivery service for secure audit report distribution.

This module combines Supabase storage with secure link generation to provide
a complete report delivery system for the Stripe webhook flow.
Enhanced with comprehensive security features including access control,
audit logging, rate limiting, and token revocation.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Union

from leadfactory.email.delivery import EmailDeliveryService
from leadfactory.email.secure_links import SecureLinkData, SecureLinkGenerator
from leadfactory.security import (
    AccessRequest,
    PDFOperation,
    RateLimitType,
    UserRole,
    get_access_control_service,
    get_audit_logger,
    get_rate_limiter,
    get_secure_access_validator,
)
from leadfactory.storage.supabase_storage import SupabaseStorage

logger = logging.getLogger(__name__)


class ReportDeliveryService:
    """
    Service for handling complete report delivery workflow.

    Integrates PDF upload to Supabase, secure URL generation,
    and email delivery for audit reports with comprehensive security features.
    """

    def __init__(
        self,
        storage_bucket: str = "reports",
        link_expiry_hours: int = 72,
        storage=None,
        email_service=None,
        link_generator=None,
        secure_validator=None,
        access_control=None,
        audit_logger=None,
        rate_limiter=None,
    ):
        """
        Initialize the report delivery service.

        Args:
            storage_bucket: Supabase storage bucket for reports
            link_expiry_hours: Default expiry time for secure links in hours
            storage: Optional storage service for dependency injection
            email_service: Optional email service for dependency injection
            link_generator: Optional link generator for dependency injection
            secure_validator: Optional secure validator for dependency injection
            access_control: Optional access control service for dependency injection
            audit_logger: Optional audit logger for dependency injection
            rate_limiter: Optional rate limiter for dependency injection
        """
        # Initialize core services with dependency injection support
        self.storage = storage or SupabaseStorage(bucket_name=storage_bucket)
        self.link_generator = link_generator or SecureLinkGenerator()
        self.email_service = email_service or EmailDeliveryService()
        self.default_expiry_hours = link_expiry_hours

        # Initialize security components with dependency injection support
        self.secure_validator = secure_validator or get_secure_access_validator()
        self.access_control = access_control or get_access_control_service()
        self.audit_logger = audit_logger or get_audit_logger()
        self.rate_limiter = rate_limiter or get_rate_limiter()

        logger.info(
            f"Report delivery service initialized with security features (bucket: {storage_bucket})"
        )

    def upload_and_deliver_report(
        self,
        pdf_path: Union[str, Path],
        report_id: str,
        user_id: str,
        user_email: str,
        purchase_id: str,
        business_name: str,
        expiry_hours: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_role: UserRole = UserRole.CUSTOMER,
    ) -> Dict[str, any]:
        """
        Complete workflow: upload PDF, generate secure link, and send email.
        Enhanced with security validation and audit logging.

        Args:
            pdf_path: Local path to the PDF report
            report_id: Unique identifier for the report
            user_id: User who purchased the report
            user_email: Email address for delivery
            purchase_id: Stripe purchase/payment intent ID
            business_name: Name of the business in the report
            expiry_hours: Custom expiry time (uses default if not provided)
            ip_address: IP address of the request
            user_agent: User agent of the request
            user_role: Role of the user making the request

        Returns:
            Dict containing delivery status and metadata

        Raises:
            Exception: If any step of the delivery process fails
        """
        expiry_hours = expiry_hours or self.default_expiry_hours

        try:
            # Step 1: Security validation - Check access permissions and rate limits
            logger.info(
                f"Validating access for report delivery {report_id} for user {user_id}"
            )

            access_request = AccessRequest(
                user_id=user_id,
                resource_id=report_id,
                operation=PDFOperation.GENERATE,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            validation_result = self.secure_validator.validate_access_request(
                access_request
            )
            if not validation_result.valid:
                self.audit_logger.log_access_denied(
                    user_id=user_id,
                    resource_id=report_id,
                    operation=PDFOperation.GENERATE.value,
                    reason=validation_result.error_message,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise PermissionError(
                    f"Access denied: {validation_result.error_message}"
                )

            # Step 2: Upload PDF to Supabase
            logger.info(f"Uploading report {report_id} for user {user_id}")
            upload_result = self.storage.upload_pdf_report(
                pdf_path=pdf_path,
                report_id=report_id,
                user_id=user_id,
                purchase_id=purchase_id,
            )

            storage_path = upload_result["storage_path"]

            # Step 3: Generate secure access link with validation
            logger.info(f"Generating secure link for report {report_id}")
            success, secure_url, error_msg = self.secure_validator.generate_secure_url(
                user_id=user_id,
                resource_id=report_id,
                operation=PDFOperation.VIEW,
                base_url="https://your-app.com/reports/access",  # Replace with actual base URL
                expiry_hours=expiry_hours,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            if not success:
                raise Exception(f"Failed to generate secure URL: {error_msg}")

            # Step 4: Generate Supabase signed URL
            supabase_url_data = self.storage.generate_secure_report_url(
                storage_path=storage_path, expires_in_hours=expiry_hours
            )

            # Step 5: Send delivery email
            logger.info(f"Sending delivery email to {user_email}")
            email_result = self._send_delivery_email(
                user_email=user_email,
                business_name=business_name,
                secure_token=(
                    secure_url.split("token=")[-1]
                    if "token=" in secure_url
                    else secure_url
                ),
                signed_url=supabase_url_data["signed_url"],
                expires_at=supabase_url_data["expires_at"],
            )

            # Step 6: Log successful delivery
            self.audit_logger.log_access_granted(
                user_id=user_id,
                resource_id=report_id,
                operation=PDFOperation.GENERATE.value,
                ip_address=ip_address,
                user_agent=user_agent,
                additional_data={
                    "purchase_id": purchase_id,
                    "business_name": business_name,
                    "email_sent": email_result.get("success", False),
                },
            )

            # Compile delivery result
            delivery_result = {
                "status": "delivered",
                "report_id": report_id,
                "user_id": user_id,
                "purchase_id": purchase_id,
                "storage_path": storage_path,
                "secure_url": secure_url,
                "signed_url": supabase_url_data["signed_url"],
                "expires_at": supabase_url_data["expires_at"],
                "email_sent": email_result.get("success", False),
                "email_id": email_result.get("email_id"),
                "delivered_at": datetime.utcnow().isoformat(),
                "upload_metadata": upload_result,
                "security_validated": True,
                "rate_limit_info": validation_result.rate_limit_info,
            }

            logger.info(f"Successfully delivered report {report_id} to {user_email}")
            return delivery_result

        except Exception as e:
            # Log security violation if this was a permission error
            if isinstance(e, PermissionError):
                self.audit_logger.log_security_violation(
                    user_id=user_id,
                    violation_type="unauthorized_report_generation",
                    description=str(e),
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

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

    def validate_and_get_report_access(
        self,
        secure_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Validate a secure token and return report access information.
        Enhanced with comprehensive security validation.

        Args:
            secure_token: JWT token from secure link
            ip_address: IP address of the request
            user_agent: User agent of the request

        Returns:
            Dict containing validation result and access info

        Raises:
            Exception: If token is invalid or expired
        """
        try:
            # Step 1: Check if token is revoked
            if self.secure_validator.is_access_revoked(secure_token):
                self.audit_logger.log_access_denied(
                    user_id="unknown",
                    resource_id="unknown",
                    operation=PDFOperation.VIEW.value,
                    reason="Token revoked",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                return {"valid": False, "error": "Access token has been revoked"}

            # Step 2: Validate the secure link token
            link_data = self.link_generator.validate_secure_link(secure_token)

            # Step 3: Create access request for validation
            access_request = AccessRequest(
                user_id=link_data.user_id,
                resource_id=link_data.report_id,
                operation=PDFOperation.VIEW,
                ip_address=ip_address,
                user_agent=user_agent,
                token=secure_token,
            )

            # Step 4: Validate access permissions and rate limits
            validation_result = self.secure_validator.validate_access_request(
                access_request
            )
            if not validation_result.valid:
                return {"valid": False, "error": validation_result.error_message}

            # Step 5: Get storage path from metadata
            storage_path = link_data.metadata.get("storage_path")
            if not storage_path:
                self.audit_logger.log_security_violation(
                    user_id=link_data.user_id,
                    violation_type="invalid_token_metadata",
                    description="Storage path not found in token metadata",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise ValueError("Storage path not found in token metadata")

            # Step 6: Generate a fresh signed URL for access
            # This provides additional security by generating a new URL each time
            fresh_url_data = self.storage.generate_secure_report_url(
                storage_path=storage_path,
                expires_in_hours=1,  # Short-lived URL for immediate download
            )

            # Step 7: Log successful access
            self.audit_logger.log_access_granted(
                user_id=link_data.user_id,
                resource_id=link_data.report_id,
                operation=PDFOperation.VIEW.value,
                ip_address=ip_address,
                user_agent=user_agent,
                additional_data={
                    "access_type": link_data.access_type,
                    "purchase_id": link_data.purchase_id,
                },
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
                "security_validated": True,
                "rate_limit_info": validation_result.rate_limit_info,
            }

        except Exception as e:
            # Log security violation for invalid token attempts
            self.audit_logger.log_security_violation(
                user_id="unknown",
                violation_type="invalid_token_access",
                description=f"Failed to validate secure token: {str(e)}",
                ip_address=ip_address,
                user_agent=user_agent,
                additional_data={
                    "token_prefix": secure_token[:10] if secure_token else "empty"
                },
            )

            logger.error(f"Failed to validate secure token: {e}")
            return {"valid": False, "error": str(e)}

    def revoke_report_access(
        self,
        token: str,
        reason: str,
        revoked_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Revoke access for a specific report token.

        Args:
            token: Token to revoke
            reason: Reason for revocation
            revoked_by: ID of user who revoked the token
            ip_address: IP address of the request
            user_agent: User agent of the request

        Returns:
            Dict containing revocation result
        """
        try:
            # Revoke the token
            success = self.secure_validator.revoke_access(
                token=token, reason=reason, revoked_by=revoked_by
            )

            if success:
                # Log the revocation
                self.audit_logger.log_token_revoked(
                    user_id=revoked_by or "system",
                    token_id=token[:10],
                    reason=reason,
                    revoked_by=revoked_by,
                    additional_data={
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                    },
                )

                return {
                    "success": True,
                    "message": "Access token revoked successfully",
                    "token_id": token[:10],
                    "revoked_at": datetime.utcnow().isoformat(),
                }
            else:
                return {"success": False, "error": "Failed to revoke access token"}

        except Exception as e:
            logger.error(f"Failed to revoke access token: {e}")
            return {"success": False, "error": str(e)}

    def get_user_access_stats(self, user_id: str) -> Dict[str, any]:
        """
        Get access statistics and security info for a user.

        Args:
            user_id: User identifier

        Returns:
            Dict containing user access statistics
        """
        try:
            # Get rate limiting stats
            rate_stats = self.rate_limiter.get_user_stats(user_id)

            # Get access control stats
            access_stats = self.secure_validator.get_access_stats(user_id)

            return {
                "user_id": user_id,
                "rate_limiting": rate_stats,
                "access_control": access_stats,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get user access stats: {e}")
            return {"error": str(e)}

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
