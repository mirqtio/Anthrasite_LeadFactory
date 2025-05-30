#!/usr/bin/env python3
"""
Script to validate scoring configuration for CI.
"""

import os
import sys
from pathlib import Path


def main():
    """Validate the scoring configuration."""

    config_path = "etc/scoring_rules.yml"

    if not os.path.exists(config_path):
        return 1

    try:
        from leadfactory.scoring import ScoringRulesParser

        parser = ScoringRulesParser(config_path)
        parser.load_and_validate()

        return 0

    except Exception:
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
