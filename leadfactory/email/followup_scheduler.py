"""Follow-up email scheduler for automated outreach campaigns.

Implements EM-3: Follow-up Auto-Send functionality.
- Schedules and manages follow-up email sequences
- Tracks engagement and adjusts sending behavior
- Handles unsubscribe and bounce management
- Provides configurable follow-up intervals and templates
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class FollowUpStatus(Enum):
    """Status values for follow-up campaigns."""

    SCHEDULED = "scheduled"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EngagementLevel(Enum):
    """Engagement level based on recipient behavior."""

    HIGH = "high"  # Opened, clicked, or replied
    MEDIUM = "medium"  # Opened but no further action
    LOW = "low"  # Delivered but not opened
    UNKNOWN = "unknown"  # Status not available


@dataclass
class FollowUpTemplate:
    """Template configuration for follow-up emails."""

    template_id: str
    name: str
    subject_line: str
    content: str
    delay_days: int
    engagement_threshold: str  # Minimum engagement level to send
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)


@dataclass
class FollowUpCampaign:
    """Follow-up campaign configuration."""

    campaign_id: str
    business_id: int
    initial_email_id: str
    templates: List[FollowUpTemplate]
    max_follow_ups: int = 3
    respect_unsubscribe: bool = True
    skip_if_engaged: bool = True
    created_at: datetime = None
    is_active: bool = True

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["templates"] = [t.to_dict() for t in self.templates]
        if isinstance(data["created_at"], datetime):
            data["created_at"] = data["created_at"].isoformat()
        return data


@dataclass
class ScheduledFollowUp:
    """Individual scheduled follow-up email."""

    follow_up_id: str
    campaign_id: str
    business_id: int
    recipient_email: str
    template_id: str
    scheduled_for: datetime
    status: FollowUpStatus = FollowUpStatus.SCHEDULED
    attempt_count: int = 0
    last_attempt: Optional[datetime] = None
    engagement_level: EngagementLevel = EngagementLevel.UNKNOWN
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["status"] = (
            data["status"].value
            if isinstance(data["status"], FollowUpStatus)
            else data["status"]
        )
        data["engagement_level"] = (
            data["engagement_level"].value
            if isinstance(data["engagement_level"], EngagementLevel)
            else data["engagement_level"]
        )
        if isinstance(data["scheduled_for"], datetime):
            data["scheduled_for"] = data["scheduled_for"].isoformat()
        if isinstance(data["created_at"], datetime):
            data["created_at"] = data["created_at"].isoformat()
        if data["last_attempt"] and isinstance(data["last_attempt"], datetime):
            data["last_attempt"] = data["last_attempt"].isoformat()
        return data


class FollowUpScheduler:
    """Service for managing automated follow-up email campaigns."""

    def __init__(self):
        """Initialize the follow-up scheduler."""
        self.storage = get_storage_instance()
        logger.info("Initialized FollowUpScheduler")

    def create_campaign(
        self,
        business_id: int,
        initial_email_id: str,
        templates: List[Dict[str, Any]],
        max_follow_ups: int = 3,
    ) -> str:
        """Create a new follow-up campaign.

        Args:
            business_id: ID of the business
            initial_email_id: ID of the initial outreach email
            templates: List of follow-up email templates
            max_follow_ups: Maximum number of follow-ups to send

        Returns:
            Campaign ID
        """
        try:
            import uuid

            campaign_id = str(uuid.uuid4())

            # Create template objects
            follow_up_templates = []
            for i, template_data in enumerate(templates):
                template = FollowUpTemplate(
                    template_id=f"{campaign_id}_template_{i+1}",
                    name=template_data.get("name", f"Follow-up {i+1}"),
                    subject_line=template_data["subject_line"],
                    content=template_data["content"],
                    delay_days=template_data.get(
                        "delay_days", (i + 1) * 7
                    ),  # Default 7 day intervals
                    engagement_threshold=template_data.get(
                        "engagement_threshold", "low"
                    ),
                )
                follow_up_templates.append(template)

            # Create campaign
            campaign = FollowUpCampaign(
                campaign_id=campaign_id,
                business_id=business_id,
                initial_email_id=initial_email_id,
                templates=follow_up_templates,
                max_follow_ups=max_follow_ups,
            )

            # Store campaign
            self.storage.create_followup_campaign(campaign.to_dict())

            logger.info(
                f"Created follow-up campaign {campaign_id} for business {business_id}"
            )
            return campaign_id

        except Exception as e:
            logger.error(f"Error creating follow-up campaign: {e}")
            raise

    def schedule_follow_ups(
        self, campaign_id: str, recipient_emails: List[str]
    ) -> List[str]:
        """Schedule follow-up emails for a list of recipients.

        Args:
            campaign_id: Campaign to schedule follow-ups for
            recipient_emails: List of email addresses

        Returns:
            List of scheduled follow-up IDs
        """
        try:
            # Get campaign details
            campaign_data = self.storage.get_followup_campaign(campaign_id)
            if not campaign_data:
                raise ValueError(f"Campaign {campaign_id} not found")

            scheduled_ids = []

            for recipient_email in recipient_emails:
                # Check if recipient is unsubscribed
                if self._is_unsubscribed(recipient_email):
                    logger.info(f"Skipping unsubscribed recipient: {recipient_email}")
                    continue

                # Schedule follow-ups for each template
                for template_data in campaign_data["templates"]:
                    if not template_data.get("is_active", True):
                        continue

                    import uuid

                    follow_up_id = str(uuid.uuid4())

                    # Calculate scheduled time
                    scheduled_for = datetime.utcnow() + timedelta(
                        days=template_data["delay_days"]
                    )

                    scheduled_follow_up = ScheduledFollowUp(
                        follow_up_id=follow_up_id,
                        campaign_id=campaign_id,
                        business_id=campaign_data["business_id"],
                        recipient_email=recipient_email,
                        template_id=template_data["template_id"],
                        scheduled_for=scheduled_for,
                    )

                    # Store scheduled follow-up
                    self.storage.create_scheduled_followup(
                        scheduled_follow_up.to_dict()
                    )
                    scheduled_ids.append(follow_up_id)

            logger.info(
                f"Scheduled {len(scheduled_ids)} follow-ups for campaign {campaign_id}"
            )
            return scheduled_ids

        except Exception as e:
            logger.error(f"Error scheduling follow-ups: {e}")
            raise

    def process_pending_follow_ups(self, limit: int = 100) -> Dict[str, int]:
        """Process pending follow-up emails that are due to be sent.

        Args:
            limit: Maximum number of follow-ups to process

        Returns:
            Dictionary with processing statistics
        """
        try:
            stats = {"processed": 0, "sent": 0, "skipped": 0, "failed": 0}

            # Get pending follow-ups that are due
            pending_follow_ups = self.storage.get_pending_followups(
                due_before=datetime.utcnow(), limit=limit
            )

            for follow_up_data in pending_follow_ups:
                stats["processed"] += 1

                try:
                    result = self._process_follow_up(follow_up_data)
                    stats[result] += 1

                except Exception as e:
                    logger.error(
                        f"Error processing follow-up {follow_up_data.get('follow_up_id')}: {e}"
                    )
                    stats["failed"] += 1

                    # Update status to failed
                    self.storage.update_followup_status(
                        follow_up_data["follow_up_id"],
                        FollowUpStatus.FAILED.value,
                        error_message=str(e),
                    )

            logger.info(f"Processed {stats['processed']} follow-ups: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error processing pending follow-ups: {e}")
            return {"processed": 0, "sent": 0, "skipped": 0, "failed": 0}

    def _process_follow_up(self, follow_up_data: Dict[str, Any]) -> str:
        """Process an individual follow-up email.

        Args:
            follow_up_data: Follow-up data from storage

        Returns:
            Processing result: 'sent', 'skipped', or 'failed'
        """
        follow_up_id = follow_up_data["follow_up_id"]
        recipient_email = follow_up_data["recipient_email"]

        # Check if recipient is unsubscribed
        if self._is_unsubscribed(recipient_email):
            self.storage.update_followup_status(
                follow_up_id, FollowUpStatus.SKIPPED.value, "Recipient unsubscribed"
            )
            return "skipped"

        # Check engagement level
        engagement = self._get_engagement_level(
            follow_up_data["campaign_id"], recipient_email
        )

        # Get template and check engagement threshold
        template_data = self.storage.get_followup_template(
            follow_up_data["template_id"]
        )
        if not template_data:
            raise ValueError(f"Template {follow_up_data['template_id']} not found")

        threshold = template_data.get("engagement_threshold", "low")
        if not self._meets_engagement_threshold(engagement, threshold):
            self.storage.update_followup_status(
                follow_up_id,
                FollowUpStatus.SKIPPED.value,
                "Engagement threshold not met",
            )
            return "skipped"

        # Get campaign details
        campaign_data = self.storage.get_followup_campaign(
            follow_up_data["campaign_id"]
        )
        if not campaign_data or not campaign_data.get("is_active", True):
            self.storage.update_followup_status(
                follow_up_id, FollowUpStatus.SKIPPED.value, "Campaign inactive"
            )
            return "skipped"

        # Skip if highly engaged (if configured)
        if (
            campaign_data.get("skip_if_engaged", True)
            and engagement == EngagementLevel.HIGH
        ):
            self.storage.update_followup_status(
                follow_up_id, FollowUpStatus.SKIPPED.value, "Recipient highly engaged"
            )
            return "skipped"

        # Send the follow-up email
        success = self._send_follow_up_email(
            follow_up_data, template_data, campaign_data
        )

        if success:
            self.storage.update_followup_status(
                follow_up_id, FollowUpStatus.SENT.value, "Successfully sent"
            )
            return "sent"
        else:
            self.storage.update_followup_status(
                follow_up_id, FollowUpStatus.FAILED.value, "Send failed"
            )
            return "failed"

    def _send_follow_up_email(
        self,
        follow_up_data: Dict[str, Any],
        template_data: Dict[str, Any],
        campaign_data: Dict[str, Any],
    ) -> bool:
        """Send a follow-up email.

        Args:
            follow_up_data: Follow-up details
            template_data: Email template
            campaign_data: Campaign configuration

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Import email delivery service
            from leadfactory.email.delivery import EmailDeliveryService

            delivery_service = EmailDeliveryService()

            # Get business data for personalization
            business = self.storage.get_business_by_id(campaign_data["business_id"])
            if not business:
                logger.error(f"Business {campaign_data['business_id']} not found")
                return False

            # Personalize email content
            subject = self._personalize_content(
                template_data["subject_line"], business, follow_up_data
            )
            content = self._personalize_content(
                template_data["content"], business, follow_up_data
            )

            # Send email using delivery service
            result = delivery_service.send_email(
                to_email=follow_up_data["recipient_email"],
                subject=subject,
                body=content,
                from_name=business.get("name", "LeadFactory"),
                email_type="follow_up",
            )

            if result.get("success"):
                logger.info(
                    f"Sent follow-up email {follow_up_data['follow_up_id']} to {follow_up_data['recipient_email']}"
                )
                return True
            else:
                logger.error(
                    f"Failed to send follow-up email: {result.get('error', 'Unknown error')}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending follow-up email: {e}")
            return False

    def _personalize_content(
        self, content: str, business: Dict[str, Any], follow_up_data: Dict[str, Any]
    ) -> str:
        """Personalize email content with business and recipient data.

        Args:
            content: Template content
            business: Business data
            follow_up_data: Follow-up data

        Returns:
            Personalized content
        """
        try:
            # Replace business placeholders
            personalized = content.replace("{business_name}", business.get("name", ""))
            personalized = personalized.replace(
                "{business_website}", business.get("website", "")
            )

            # Replace recipient placeholders
            recipient_name = follow_up_data.get(
                "recipient_name", follow_up_data["recipient_email"].split("@")[0]
            )
            personalized = personalized.replace("{recipient_name}", recipient_name)

            # Add unsubscribe link
            unsubscribe_url = f"{business.get('website', '')}/unsubscribe?email={follow_up_data['recipient_email']}&campaign={follow_up_data['campaign_id']}"
            personalized = personalized.replace("{unsubscribe_url}", unsubscribe_url)

            return personalized

        except Exception as e:
            logger.error(f"Error personalizing content: {e}")
            return content

    def _is_unsubscribed(self, email: str) -> bool:
        """Check if an email address is unsubscribed.

        Args:
            email: Email address to check

        Returns:
            True if unsubscribed, False otherwise
        """
        try:
            return self.storage.is_email_unsubscribed(email)
        except Exception as e:
            logger.error(f"Error checking unsubscribe status for {email}: {e}")
            return False  # Default to not unsubscribed if error

    def _get_engagement_level(self, campaign_id: str, email: str) -> EngagementLevel:
        """Get engagement level for a recipient.

        Args:
            campaign_id: Campaign ID
            email: Recipient email

        Returns:
            Engagement level
        """
        try:
            engagement_data = self.storage.get_email_engagement(campaign_id, email)

            if not engagement_data:
                return EngagementLevel.UNKNOWN

            # Check for high engagement (replied, clicked, etc.)
            if (
                engagement_data.get("replied", False)
                or engagement_data.get("clicked", False)
                or engagement_data.get("forwarded", False)
            ):
                return EngagementLevel.HIGH

            # Check for medium engagement (opened)
            if engagement_data.get("opened", False):
                return EngagementLevel.MEDIUM

            # Check for low engagement (delivered but not opened)
            if engagement_data.get("delivered", False):
                return EngagementLevel.LOW

            return EngagementLevel.UNKNOWN

        except Exception as e:
            logger.error(f"Error getting engagement level: {e}")
            return EngagementLevel.UNKNOWN

    def _meets_engagement_threshold(
        self, engagement: EngagementLevel, threshold: str
    ) -> bool:
        """Check if engagement meets the required threshold.

        Args:
            engagement: Current engagement level
            threshold: Required threshold (high, medium, low)

        Returns:
            True if threshold is met, False otherwise
        """
        engagement_scores = {
            EngagementLevel.HIGH: 3,
            EngagementLevel.MEDIUM: 2,
            EngagementLevel.LOW: 1,
            EngagementLevel.UNKNOWN: 0,
        }

        threshold_scores = {"high": 3, "medium": 2, "low": 1, "none": 0}

        required_score = threshold_scores.get(threshold.lower(), 1)
        current_score = engagement_scores.get(engagement, 0)

        return current_score >= required_score

    def cancel_campaign(
        self, campaign_id: str, reason: str = "Manually cancelled"
    ) -> bool:
        """Cancel a follow-up campaign and all pending follow-ups.

        Args:
            campaign_id: Campaign to cancel
            reason: Cancellation reason

        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            # Cancel campaign
            self.storage.update_campaign_status(campaign_id, False, reason)

            # Cancel all pending follow-ups for this campaign
            cancelled_count = self.storage.cancel_pending_followups(campaign_id, reason)

            logger.info(
                f"Cancelled campaign {campaign_id} and {cancelled_count} pending follow-ups"
            )
            return True

        except Exception as e:
            logger.error(f"Error cancelling campaign {campaign_id}: {e}")
            return False

    def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Get statistics for a follow-up campaign.

        Args:
            campaign_id: Campaign ID

        Returns:
            Campaign statistics
        """
        try:
            return self.storage.get_followup_campaign_stats(campaign_id)
        except Exception as e:
            logger.error(f"Error getting campaign stats for {campaign_id}: {e}")
            return {}

    def update_engagement(
        self,
        campaign_id: str,
        email: str,
        engagement_type: str,
        timestamp: datetime = None,
    ) -> bool:
        """Update engagement tracking for a recipient.

        Args:
            campaign_id: Campaign ID
            email: Recipient email
            engagement_type: Type of engagement (opened, clicked, replied, etc.)
            timestamp: When the engagement occurred

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            if timestamp is None:
                timestamp = datetime.utcnow()

            self.storage.update_email_engagement(
                campaign_id, email, engagement_type, timestamp
            )

            logger.info(
                f"Updated engagement for {email} in campaign {campaign_id}: {engagement_type}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating engagement: {e}")
            return False
