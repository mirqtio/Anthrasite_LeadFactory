#!/usr/bin/env python
"""
Setup E2E Environment

This script copies API keys and other settings from the root .env file
to the .env.e2e file while ensuring EMAIL_OVERRIDE is properly set.
"""

import os
import re
import sys
import time
from pathlib import Path

# Keys to copy from .env to .env.e2e
KEYS_TO_COPY = [
    # SendGrid related keys
    "SENDGRID_KEY",
    "SENDGRID_FROM_EMAIL",
    "SENDGRID_DEDICATED_IP_POOL",
    "SENDGRID_SHARED_IP_POOL",
    # Screenshot related keys
    "SCREENSHOT_ONE_KEY",
    # API keys
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "YELP_API_KEY",
    "GOOGLE_API_KEY",
    "PAGESPEED_KEY",
    "SEMRUSH_KEY",
    # Database settings
    "DATABASE_URL",
    "DATABASE_POOL_MIN_CONN",
    "DATABASE_POOL_MAX_CONN",
    # Supabase configuration
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_BUCKET",
    # Other settings
    "TIER",
    "LOG_FORMAT",
]

# Settings to force in .env.e2e regardless of .env values
FORCED_SETTINGS = {
    "EMAIL_OVERRIDE": "charlie@anthrasite.io",
    "MOCKUP_ENABLED": "true",
    "TEST_MODE": "false",
    "USE_MOCKS": "false",
    "DEBUG_MODE": "true",
    "LOG_LEVEL": "DEBUG",
    "ENVIRONMENT": "e2e_testing",
}


def parse_env_file(file_path):
    """Parse an env file and return a dictionary of keys and values."""
    result = {}
    try:
        with open(file_path) as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r"^([A-Za-z0-9_]+)=(.*)$", line)
            if match:
                key, value = match.groups()
                result[key] = value

    except Exception:
        pass

    return result


def update_e2e_env_file(source_env, target_e2e_env, keys_to_copy, forced_settings):
    """Update the .env.e2e file with values from .env"""
    # Read existing .env.e2e file
    e2e_env_data = (
        parse_env_file(target_e2e_env) if os.path.exists(target_e2e_env) else {}
    )

    # Read values from .env
    env_data = parse_env_file(source_env)

    # Keep track of which keys were copied
    copied_keys = []

    # Backup the current .env.e2e file if it exists
    if os.path.exists(target_e2e_env):
        backup_path = f"{target_e2e_env}.bak.{int(time.time())}"
        try:
            with open(target_e2e_env) as src, open(backup_path, "w") as dst:
                dst.write(src.read())
        except Exception:
            pass

    # Update e2e_env_data with values from env_data
    for key in keys_to_copy:
        if key in env_data and env_data[key]:
            e2e_env_data[key] = env_data[key]
            copied_keys.append(key)

    # Force specific settings
    for key, value in forced_settings.items():
        e2e_env_data[key] = value

    # Write updated .env.e2e file
    try:
        with open(target_e2e_env, "w") as f:
            f.write("# Anthrasite Lead-Factory Phase 0\n")
            f.write("# End-to-End Testing Environment Configuration\n")
            f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("#\n")
            f.write("# IMPORTANT: This file contains real API keys for E2E testing.\n")
            f.write("# DO NOT commit this file to version control.\n")
            f.write("# This environment is intended for local E2E testing only.\n\n")

            # Write forced settings first with explanations
            f.write("# E2E Test Settings (forced values)\n")
            f.write("# -------------------------\n")
            for key, value in forced_settings.items():
                f.write(f"{key}={value}\n")
            f.write("\n")

            # Write copied API keys
            f.write("# API Keys (copied from .env)\n")
            f.write("# ---------------------------\n")
            for key in keys_to_copy:
                if key in e2e_env_data:
                    f.write(f"{key}={e2e_env_data[key]}\n")

        # Report any missing keys
        missing_keys = [
            key for key in keys_to_copy if key not in env_data or not env_data[key]
        ]
        if missing_keys:
            for key in missing_keys:
                pass

    except Exception:
        return False

    return True


def main():
    # Get paths
    project_root = Path(__file__).resolve().parent.parent
    source_env = project_root / ".env"
    target_e2e_env = project_root / ".env.e2e"

    # Check if .env exists
    if not source_env.exists():
        return 1

    # Update .env.e2e
    success = update_e2e_env_file(
        source_env, target_e2e_env, KEYS_TO_COPY, FORCED_SETTINGS
    )

    if success:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
