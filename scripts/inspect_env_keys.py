#!/usr/bin/env python3
"""
Inspect environment variable keys from .env file

This script prints only the variable names from the .env file,
without exposing their values, to help identify the actual key names.
"""

import os
import re
from pathlib import Path


def get_env_keys(env_file):
    """Extract only the key names from an .env file."""
    keys = []
    try:
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                match = re.match(r"^([A-Za-z0-9_]+)=", line)
                if match:
                    key = match.group(1)
                    keys.append(key)
    except Exception as e:
        print(f"Error reading {env_file}: {e}")

    return keys


def main():
    # Get path to .env file
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"

    if not env_file.exists():
        print(f"Error: {env_file} not found!")
        return 1

    # Get key names only
    keys = get_env_keys(env_file)

    if not keys:
        print("No keys found in .env file")
        return 1

    # Group keys by prefix
    key_groups = {}
    for key in keys:
        prefix = key.split("_")[0].lower() if "_" in key else key.lower()
        if prefix not in key_groups:
            key_groups[prefix] = []
        key_groups[prefix].append(key)

    # Print keys by group
    print("\nEnvironment variable keys found in .env:")
    print("----------------------------------------")
    for prefix, prefix_keys in sorted(key_groups.items()):
        print(f"\n{prefix.upper()} related keys:")
        for key in sorted(prefix_keys):
            print(f"  - {key}")

    # Print some specific keys we're looking for
    important_prefixes = ["sendgrid", "screenshot", "openai", "yelp", "google"]
    print("\nKeys relevant for E2E testing:")
    print("-----------------------------")
    for prefix in important_prefixes:
        if prefix in key_groups:
            print(f"\n{prefix.upper()} keys:")
            for key in sorted(key_groups[prefix]):
                print(f"  - {key}")
        else:
            print(f"\nNo {prefix.upper()} keys found")

    return 0


if __name__ == "__main__":
    main()
