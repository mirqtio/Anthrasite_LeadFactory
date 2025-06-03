"""
Email module for SendGrid integration and IP warm-up management.
"""

from .sendgrid_warmup import (
    SendGridWarmupScheduler,
    WarmupConfiguration,
    WarmupProgress,
    WarmupStage,
    WarmupStatus,
    advance_warmup_if_needed,
    check_warmup_limits,
    get_warmup_scheduler,
    record_warmup_emails_sent,
)

__all__ = [
    "SendGridWarmupScheduler",
    "WarmupConfiguration",
    "WarmupProgress",
    "WarmupStatus",
    "WarmupStage",
    "get_warmup_scheduler",
    "check_warmup_limits",
    "record_warmup_emails_sent",
    "advance_warmup_if_needed",
]
