#!/usr/bin/env python3
"""
Script to validate scoring configuration for CI.
"""

import sys
import os
from pathlib import Path


def main():
    """Validate the scoring configuration."""
    print("Validating scoring rules configuration...")
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {os.getcwd()}")

    config_path = "etc/scoring_rules.yml"
    print(f"Checking for config file: {config_path}")
    print(f"File exists: {os.path.exists(config_path)}")

    if not os.path.exists(config_path):
        print(f"✗ Configuration file not found: {config_path}")
        return 1

    try:
        from leadfactory.scoring import ScoringRulesParser

        parser = ScoringRulesParser(config_path)
        config = parser.load_and_validate()

        print("✓ Scoring configuration is valid")
        print(f"  - {len(config.rules)} rules loaded")
        print(f"  - {len(config.multipliers)} multipliers loaded")

        return 0

    except Exception as e:
        print(f"✗ Configuration error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
