#!/usr/bin/env python3
"""
Script to properly fix the test_mockup_unit.py file.
"""

import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fix_test_mockup_unit():
    """Fix the broken syntax in test_mockup_unit.py."""
    # First, let's restore the original file from git
    subprocess.run(["git", "checkout", "--", "tests/test_mockup_unit.py"])

    # Now let's fix the file properly
    file_path = Path("tests/test_mockup_unit.py")

    with file_path.open() as f:
        content = f.read()

    # Fix the undefined names by adding proper mock variables
    content = content.replace(
        'patch(\n        "bin.mockup.logger"\n    ):',
        'patch(\n        "bin.mockup.logger"\n    ) as mock_logging:',
    )

    content = content.replace(
        'patch(\n        "utils.io.track_api_cost"\n    ),',
        'patch(\n        "utils.io.track_api_cost"\n    ) as mock_track,',
    )

    with file_path.open("w") as f:
        f.write(content)

    logger.info("Fixed test_mockup_unit.py")


if __name__ == "__main__":
    fix_test_mockup_unit()
