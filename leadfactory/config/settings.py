"""
Configuration settings for LeadFactory.

This module contains all configuration settings for the LeadFactory application,
loaded from environment variables with appropriate type conversion and defaults.
"""

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# Import the environment loading helpers directly from __init__.py
from leadfactory.config import (
    get_boolean_env,
    get_env,
    get_float_env,
    get_int_env,
)

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = get_env("DATA_DIR", str(BASE_DIR / "data"))
LOGS_DIR = get_env("LOGS_DIR", str(BASE_DIR / "logs"))

# Ensure directories exist
Path(DATA_DIR).mkdir(exist_ok=True)
Path(LOGS_DIR).mkdir(exist_ok=True)

# Environment
ENVIRONMENT = get_env("ENVIRONMENT", "development")
TIER = get_int_env("TIER", 1)

# ==================
# API Keys
# ==================
YELP_API_KEY = get_env("YELP_KEY")
GOOGLE_PLACES_API_KEY = get_env("GOOGLE_KEY")
SCREENSHOTONE_API_KEY = get_env("SCREENSHOT_ONE_KEY")
PAGESPEED_API_KEY = get_env("PAGESPEED_KEY")
SEMRUSH_API_KEY = get_env("SEMRUSH_KEY")

# Email configuration
SENDGRID_API_KEY = get_env("SENDGRID_KEY")
SENDGRID_FROM_EMAIL = get_env("SENDGRID_FROM_EMAIL", "outreach@anthrasite.com")
SENDGRID_FROM_NAME = get_env("SENDGRID_FROM_NAME", "Anthrasite Lead Factory")
SENDGRID_SHARED_IP_POOL = get_env("SENDGRID_SHARED_IP_POOL", "shared")
SENDGRID_DEDICATED_IP_POOL = get_env("SENDGRID_DEDICATED_IP_POOL", "dedicated")

# LLM configuration
OPENAI_API_KEY = get_env("OPENAI_API_KEY")
OPENAI_MODEL = get_env("OPENAI_MODEL", "gpt-4o")
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = get_env("ANTHROPIC_MODEL", "claude-3-opus-20240229")
OLLAMA_HOST = get_env("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = get_env("OLLAMA_MODEL", "llama3:8b")
LLM_MODEL_VERSION = get_env("LLM_MODEL_VERSION", "gpt-4o")

# ==================
# Database
# ==================
DATABASE_URL = get_env("DATABASE_URL", "sqlite:///leadfactory.db")
DATABASE_PATH = get_env("DATABASE_PATH", "leadfactory.db")
DATABASE_POOL_MIN_CONN = get_int_env("DATABASE_POOL_MIN_CONN", 2)
DATABASE_POOL_MAX_CONN = get_int_env("DATABASE_POOL_MAX_CONN", 10)

# Supabase
SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_KEY = get_env("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = get_env("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = get_env("SUPABASE_BUCKET", "mockups")

# ==================
# Application
# ==================
MOCKUP_ENABLED = get_boolean_env("MOCKUP_ENABLED", False)
MAX_LEADS_PER_BATCH = get_int_env("MAX_LEADS_PER_BATCH", 100)
MAX_CONCURRENT_REQUESTS = get_int_env("MAX_CONCURRENT_REQUESTS", 10)
REQUEST_TIMEOUT_SECONDS = get_int_env("REQUEST_TIMEOUT_SECONDS", 30)

# ==================
# Batch Processing
# ==================
BATCH_TRACKER_FILE = get_env(
    "BATCH_TRACKER_FILE", str(Path(DATA_DIR) / "batch_tracker.json")
)
BATCH_COMPLETION_DEADLINE_HOUR = get_int_env("BATCH_COMPLETION_DEADLINE_HOUR", 5)
BATCH_COMPLETION_DEADLINE_MINUTE = get_int_env("BATCH_COMPLETION_DEADLINE_MINUTE", 0)
BATCH_COMPLETION_TIMEZONE = get_env("BATCH_COMPLETION_TIMEZONE", "America/New_York")
BATCH_COMPLETION_CHECK_INTERVAL = get_int_env(
    "BATCH_COMPLETION_CHECK_INTERVAL_SECONDS", 300
)
BATCH_METRICS_UPDATE_INTERVAL = get_int_env("BATCH_METRICS_UPDATE_INTERVAL", 60)

# ==================
# Budget
# ==================
MONTHLY_BUDGET = get_float_env("MONTHLY_BUDGET", 250.0)
DAILY_BUDGET = get_float_env("DAILY_BUDGET", 10.0)
MONTHLY_THRESHOLD = get_float_env("MONTHLY_THRESHOLD", 0.8)
DAILY_THRESHOLD = get_float_env("DAILY_THRESHOLD", 0.8)
BUDGET_GATE_ENABLED = get_boolean_env("BUDGET_GATE_ENABLED", True)
BUDGET_GATE_THRESHOLD = get_float_env("BUDGET_GATE_THRESHOLD", 1000.0)
BUDGET_GATE_OVERRIDE = get_boolean_env("BUDGET_GATE_OVERRIDE", False)

# ==================
# Alerts
# ==================
ALERT_EMAIL_TO = get_env("ALERT_EMAIL_TO", "alerts@anthrasite.com")
ALERT_EMAIL_FROM = get_env("ALERT_EMAIL_FROM", "leadfactory@anthrasite.com")
SMTP_SERVER = get_env("SMTP_SERVER", "smtp.sendgrid.net")
SMTP_PORT = get_int_env("SMTP_PORT", 587)
SMTP_USERNAME = get_env("SMTP_USERNAME", "apikey")
SMTP_PASSWORD = get_env("SMTP_PASSWORD", get_env("SENDGRID_API_KEY", ""))
ALERT_BATCH_COMPLETION_DELAY = get_boolean_env("ALERT_BATCH_COMPLETION_DELAY", True)
ALERT_COST_THRESHOLD = get_float_env("ALERT_COST_THRESHOLD", 3.0)
ALERT_COST_TIER2_THRESHOLD = get_float_env("ALERT_COST_TIER2_THRESHOLD", 6.0)
ALERT_COST_TIER3_THRESHOLD = get_float_env("ALERT_COST_TIER3_THRESHOLD", 10.0)
ALERT_GPU_BURST_THRESHOLD = get_float_env("ALERT_GPU_BURST_THRESHOLD", 25.0)


# ==================
# Helper functions
# ==================
def get_tiered_value(
    tier1_value: Any, tier2_value: Any = None, tier3_value: Any = None
) -> Any:
    """
    Return value based on the configured tier level.

    Args:
        tier1_value: Value to use for tier 1
        tier2_value: Value to use for tier 2. If None, uses tier1_value
        tier3_value: Value to use for tier 3. If None, uses tier2_value

    Returns:
        The appropriate value for the current tier
    """
    if tier2_value is None:
        tier2_value = tier1_value

    if tier3_value is None:
        tier3_value = tier2_value

    if TIER == 1:
        return tier1_value
    elif TIER == 2:
        return tier2_value
    else:
        return tier3_value


def get_alert_threshold(tier: Optional[int] = None) -> float:
    """
    Get the cost alert threshold for the specified tier or current tier.

    Args:
        tier: Tier level (1, 2, or 3). If None, uses TIER

    Returns:
        The cost threshold for the specified tier
    """
    tier = tier or TIER

    if tier == 1:
        return ALERT_COST_THRESHOLD
    elif tier == 2:
        return ALERT_COST_TIER2_THRESHOLD
    else:
        return ALERT_COST_TIER3_THRESHOLD


def is_production() -> bool:
    """Check if the current environment is production."""
    return ENVIRONMENT.lower() == "production"


def is_development() -> bool:
    """Check if the current environment is development."""
    return ENVIRONMENT.lower() == "development"


def is_staging() -> bool:
    """Check if the current environment is staging."""
    return ENVIRONMENT.lower() == "staging"


def get_all_settings() -> Dict[str, Any]:
    """
    Get all configuration settings as a dictionary.

    Returns:
        Dictionary of all settings defined in this module
    """
    settings = {}

    # Get all uppercase variables from this module
    current_module = sys.modules[__name__]
    for name in dir(current_module):
        if name.isupper():
            settings[name] = getattr(current_module, name)

    # Add helper functions
    settings["get_tiered_value"] = get_tiered_value
    settings["get_alert_threshold"] = get_alert_threshold
    settings["is_production"] = is_production
    settings["is_development"] = is_development
    settings["is_staging"] = is_staging

    return settings
