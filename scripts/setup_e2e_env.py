#!/usr/bin/env python
"""
Setup E2E Environment

This script copies API keys and other settings from the root .env file
to the .env.e2e file while ensuring EMAIL_OVERRIDE is properly set.
"""

import os
import sys
from pathlib import Path
import re
import time

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
        with open(file_path, "r") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r"^([A-Za-z0-9_]+)=(.*)$", line)
            if match:
                key, value = match.groups()
                result[key] = value

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")

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
            with open(target_e2e_env, "r") as src, open(backup_path, "w") as dst:
                dst.write(src.read())
            print(f"Backed up existing .env.e2e to {backup_path}")
        except Exception as e:
            print(f"Warning: Failed to backup .env.e2e: {e}")

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

        print(f"Updated {target_e2e_env} successfully!")
        print(f"Copied {len(copied_keys)} keys from {source_env}")
        print(f"Set {len(forced_settings)} forced settings for E2E testing")

        # Report any missing keys
        missing_keys = [
            key for key in keys_to_copy if key not in env_data or not env_data[key]
        ]
        if missing_keys:
            print(f"\nWarning: The following keys were not found in {source_env}:")
            for key in missing_keys:
                print(f"  - {key}")
            print(
                "\nYou may need to add these manually to .env.e2e for full E2E testing functionality."
            )

    except Exception as e:
        print(f"Error writing to {target_e2e_env}: {e}")
        return False

    return True


def main():
    # Get paths
    project_root = Path(__file__).resolve().parent.parent
    source_env = project_root / ".env"
    target_e2e_env = project_root / ".env.e2e"

    # Check if .env exists
    if not source_env.exists():
        print(f"Error: {source_env} not found!")
        return 1

    # Update .env.e2e
    success = update_e2e_env_file(
        source_env, target_e2e_env, KEYS_TO_COPY, FORCED_SETTINGS
    )

    if success:
        print("\nSetup complete!")
        print("To run the E2E tests:")
        print("1. Verify the values in .env.e2e are correct")
        print("2. Run: python scripts/run_e2e_test.py")
        return 0
    else:
        print("\nSetup failed! See error messages above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
