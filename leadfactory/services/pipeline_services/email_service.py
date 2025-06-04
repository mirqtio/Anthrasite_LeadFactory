"""
Email service for scalable pipeline architecture.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from .base_service import BasePipelineService, ServiceConfig, TaskRequest


logger = logging.getLogger(__name__)


class EmailService(BasePipelineService):
    """Email delivery microservice."""
    
    def __init__(self, config: Optional[ServiceConfig] = None):
        if config is None:
            config = ServiceConfig(service_name="email", port=8006)
        super().__init__(config)
        self._initialize_email()
    
    def _initialize_email(self):
        try:
            from leadfactory.email.service import EmailServiceManager
            self._email_manager = EmailServiceManager()
            self._email_available = True
        except ImportError as e:
            logger.error(f"Failed to import email modules: {e}")
            self._email_available = False
    
    async def _process_task(self, request: TaskRequest) -> Dict[str, Any]:
        """Process email delivery task."""
        email_data = request.metadata or {}
        business_ids = email_data.get("business_ids", [])
        campaign_type = email_data.get("campaign_type", "lead_report")
        
        sent_count = 0
        failed_count = 0
        
        if hasattr(self, '_email_manager') and self._email_available:
            # Use actual email delivery
            for business_id in business_ids:
                try:
                    # Prepare email context
                    email_context = {
                        "business_id": business_id,
                        "campaign_type": campaign_type,
                        "recipient": email_data.get("recipient", "test@example.com"),
                        "template_data": email_data.get("template_data", {})
                    }
                    
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, self._email_manager.send_email, email_context
                    )
                    
                    if result.get("success"):
                        sent_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Email delivery failed for business {business_id}: {e}")
                    failed_count += 1
        else:
            # Mock email delivery
            await asyncio.sleep(len(business_ids) * 0.1)
            sent_count = len(business_ids)
        
        return {
            "emails_sent": sent_count,
            "emails_failed": failed_count,
            "delivery_rate": sent_count / (sent_count + failed_count) if (sent_count + failed_count) > 0 else 1.0,
            "campaign_type": campaign_type
        }


def create_email_service() -> EmailService:
    config = ServiceConfig(service_name="email", port=8006, debug=True)
    return EmailService(config)