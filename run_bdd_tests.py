#!/usr/bin/env python3
"""
Run BDD tests with proper environment setup.

This script ensures that all necessary paths and mocks are in place before running the BDD tests.
"""

import os
import subprocess
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent)
sys.path.insert(0, project_root)

# Add necessary paths to PYTHONPATH
os.environ["PYTHONPATH"] = f"{project_root}:{os.environ.get('PYTHONPATH', '')}"

# Set environment variables for testing
os.environ["TEST_MODE"] = "True"
os.environ["MOCK_EXTERNAL_APIS"] = "True"

# Run the tests with proper setup
if __name__ == "__main__":
    result = subprocess.run(
        [
            "python3",
            "-m",
            "pytest",
            "tests/bdd",
            "-v",
            "--no-header",
            "--tb=native",
        ]
    )

    sys.exit(result.returncode)
