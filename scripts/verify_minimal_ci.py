#!/usr/bin/env python3
"""
Verify Minimal CI Workflow

This script verifies that the minimal CI workflow components work correctly
by running them locally in the same sequence as the CI workflow.

It follows the principles of:
1. Incremental Changes: Tests each component individually
2. Evidence-Based Fixes: Provides detailed logs for each step
3. Verification: Confirms each step works before proceeding

Usage:
    python scripts/verify_minimal_ci.py [--verbose]
"""

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("verify_minimal_ci.log", mode="w"),
    ],
)

logger = logging.getLogger("verify_minimal_ci")


def run_command(command, cwd=None, env=None, timeout=300):
    """Run a command and return the result with detailed logging."""
    logger.info(f"Running command: {' '.join(command)}")

    start_time = time.time()

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        duration = time.time() - start_time
        logger.info(
            f"Command completed in {duration:.2f} seconds with exit code {result.returncode}"
        )

        if result.stdout:
            logger.debug(f"STDOUT:\n{result.stdout}")

        if result.stderr:
            logger.debug(f"STDERR:\n{result.stderr}")

        return result
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return None


def verify_minimal_test_setup():
    """Verify the minimal test environment setup script."""
    logger.info("Verifying minimal test environment setup...")

    result = run_command(
        [sys.executable, "scripts/minimal_test_setup.py", "--verbose"],
        cwd=Path(__file__).parent.parent,
    )

    if result and result.returncode == 0:
        logger.info("✅ Minimal test environment setup verified successfully")
        return True
    else:
        logger.error("❌ Minimal test environment setup failed")
        return False


def verify_minimal_test_tools():
    """Verify the minimal test tools installation script."""
    logger.info("Verifying minimal test tools installation...")

    result = run_command(
        [sys.executable, "scripts/minimal_test_tools.py", "--verbose"],
        cwd=Path(__file__).parent.parent,
    )

    if result and result.returncode == 0:
        logger.info("✅ Minimal test tools installation verified successfully")
        return True
    else:
        logger.error("❌ Minimal test tools installation failed")
        return False


def verify_minimal_test_tracker():
    """Verify the minimal test tracker script."""
    logger.info("Verifying minimal test tracker...")

    # First, just verify the script runs without the --run-tests flag
    result = run_command(
        [sys.executable, "scripts/minimal_test_tracker.py"],
        cwd=Path(__file__).parent.parent,
    )

    if result and result.returncode == 0:
        logger.info("✅ Minimal test tracker (report mode) verified successfully")

        # Now try running a very basic test to verify test execution
        logger.info("Verifying minimal test tracker with test execution...")

        # Create a simple test file for verification
        test_dir = Path(__file__).parent.parent / "tests" / "verify_ci"
        test_dir.mkdir(exist_ok=True, parents=True)

        test_file = test_dir / "test_verify_ci.py"
        with open(test_file, "w") as f:
            f.write(
                """
def test_verify_ci_simple():
    \"\"\"A simple test that always passes for CI verification.\"\"\"
    assert True
"""
            )

        # Run the test tracker with the test
        result = run_command(
            [
                sys.executable,
                "scripts/minimal_test_tracker.py",
                "--run-tests",
                "--test-pattern",
                "verify_ci/test_verify_ci.py",
            ],
            cwd=Path(__file__).parent.parent,
        )

        if result and result.returncode == 0:
            logger.info(
                "✅ Minimal test tracker (test execution) verified successfully"
            )
            return True
        else:
            logger.error("❌ Minimal test tracker (test execution) failed")
            return False
    else:
        logger.error("❌ Minimal test tracker (report mode) failed")
        return False


def verify_minimal_path_fix():
    """Verify the minimal Python path fix script."""
    logger.info("Verifying minimal Python path fix...")

    result = run_command(
        [sys.executable, "scripts/minimal_path_fix.py", "--verbose"],
        cwd=Path(__file__).parent.parent,
    )

    if result and result.returncode == 0:
        logger.info("✅ Minimal Python path fix verified successfully")
        return True
    else:
        logger.error("❌ Minimal Python path fix failed")
        return False


def verify_import_test():
    """Verify that imports work correctly after path fix."""
    logger.info("Verifying import resolution with a simple test...")

    # Create a simple test file that imports from bin and utils
    test_dir = Path(__file__).parent.parent / "tests" / "verify_imports"
    test_dir.mkdir(exist_ok=True, parents=True)

    test_file = test_dir / "test_import_resolution.py"
    test_content = """
# Test import resolution
import sys
import os
from pathlib import Path

def test_bin_imports():
    \"\"\"Test that bin modules can be imported.\"\"\"
    try:
        # Try to import a module from bin
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        import bin
        assert True
    except ImportError as e:
        print(f"Import error: {e}")
        print(f"sys.path: {sys.path}")
        assert False, f"Failed to import bin: {e}"

def test_utils_imports():
    \"\"\"Test that utils modules can be imported.\"\"\"
    try:
        # Try to import a module from utils
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        import utils
        assert True
    except ImportError as e:
        print(f"Import error: {e}")
        print(f"sys.path: {sys.path}")
        assert False, f"Failed to import utils: {e}"
"""

    with open(test_file, "w") as f:
        f.write(test_content)

    # Run the test
    result = run_command(
        [sys.executable, "-m", "pytest", str(test_file), "-v"],
        cwd=Path(__file__).parent.parent,
    )

    if result and result.returncode == 0:
        logger.info("✅ Import resolution test passed successfully")
        return True
    else:
        logger.error("❌ Import resolution test failed")
        return False


def main():
    """Main function with error handling."""
    parser = argparse.ArgumentParser(description="Verify Minimal CI Workflow")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--skip-path-fix", action="store_true", help="Skip Python path fix verification"
    )
    parser.add_argument(
        "--skip-import-test", action="store_true", help="Skip import resolution test"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    logger.info("Starting verification of minimal CI workflow components")

    # Verify each component in sequence
    setup_success = verify_minimal_test_setup()

    if not setup_success:
        logger.error("❌ Verification failed at test environment setup stage")
        return 1

    tools_success = verify_minimal_test_tools()

    if not tools_success:
        logger.error("❌ Verification failed at test tools installation stage")
        return 1

    tracker_success = verify_minimal_test_tracker()

    if not tracker_success:
        logger.error("❌ Verification failed at test tracker stage")
        return 1

    # Verify Python path fix if not skipped
    if not args.skip_path_fix:
        path_fix_success = verify_minimal_path_fix()

        if not path_fix_success:
            logger.error("❌ Verification failed at Python path fix stage")
            return 1
    else:
        logger.info("Skipping Python path fix verification as requested")

    # Verify import resolution if not skipped
    if not args.skip_import_test:
        import_test_success = verify_import_test()

        if not import_test_success:
            logger.error("❌ Verification failed at import resolution test stage")
            return 1
    else:
        logger.info("Skipping import resolution test as requested")

    # All components verified successfully
    logger.info("✅ All minimal CI workflow components verified successfully")
    logger.info("You can now push these changes to GitHub with confidence")

    return 0


if __name__ == "__main__":
    sys.exit(main())
