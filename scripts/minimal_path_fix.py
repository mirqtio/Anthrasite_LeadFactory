#!/usr/bin/env python3
"""
Minimal Python Path Fix Script

This script ensures correct Python path setup for importing project modules
in tests and scripts. It creates a .pth file in the site-packages directory
and a minimal conftest.py file for proper test configuration.

It follows the principles of:
1. Incremental Changes: Focuses only on essential path fixes
2. Evidence-Based Fixes: Based on common import issues in CI environments
3. Comprehensive Error Handling: Robust error handling for all operations

Usage:
    python scripts/minimal_path_fix.py [--verbose]
"""

import argparse
import logging
import os
import site
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def create_pth_file(project_root, verbose=False):
    """
    Create a .pth file in the site-packages directory to add the project root to Python path.

    Args:
        project_root (Path): Path to the project root directory
        verbose (bool): Whether to enable verbose logging

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Creating .pth file to add project root to Python path")

        # Get site-packages directory
        site_packages_dirs = site.getsitepackages()
        user_site = site.getusersitepackages()

        if verbose:
            logger.info(f"Site-packages directories: {site_packages_dirs}")
            logger.info(f"User site-packages directory: {user_site}")

        # Try to find a writable site-packages directory
        writable_dirs = []

        # Check system site-packages
        for site_dir in site_packages_dirs:
            if os.access(site_dir, os.W_OK):
                writable_dirs.append(site_dir)

        # Check user site-packages
        if os.access(user_site, os.W_OK):
            writable_dirs.append(user_site)

        if not writable_dirs:
            logger.error("No writable site-packages directory found")

            # Create a local directory for path configuration
            local_site_dir = project_root / ".site-packages"
            local_site_dir.mkdir(exist_ok=True)

            logger.info(f"Created local site-packages directory: {local_site_dir}")
            writable_dirs.append(str(local_site_dir))

            # Add local directory to Python path
            sys.path.insert(0, str(local_site_dir))

            # Set PYTHONPATH environment variable
            current_pythonpath = os.environ.get("PYTHONPATH", "")
            if str(local_site_dir) not in current_pythonpath:
                if current_pythonpath:
                    os.environ["PYTHONPATH"] = f"{local_site_dir}:{current_pythonpath}"
                else:
                    os.environ["PYTHONPATH"] = str(local_site_dir)
                logger.info(f"Set PYTHONPATH={os.environ['PYTHONPATH']}")

        success = False

        # Create .pth file in each writable directory
        for site_dir in writable_dirs:
            try:
                pth_file = Path(site_dir) / "anthrasite_leadfactory.pth"

                with open(pth_file, "w") as f:
                    f.write(str(project_root))

                logger.info(f"Created .pth file at {pth_file}")
                success = True

                # Break after first successful creation
                break
            except Exception as e:
                logger.warning(f"Failed to create .pth file in {site_dir}: {e}")

        if success:
            logger.info("Successfully added project root to Python path")
            return True
        else:
            logger.error("Failed to create .pth file in any site-packages directory")
            return False

    except Exception as e:
        logger.error(f"Error creating .pth file: {e}")
        return False


def create_conftest_py(project_root, verbose=False):
    """
    Create a minimal conftest.py file for proper test configuration.

    Args:
        project_root (Path): Path to the project root directory
        verbose (bool): Whether to enable verbose logging

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Creating minimal conftest.py for proper test configuration")

        conftest_path = project_root / "conftest.py"

        conftest_content = """
# Minimal conftest.py for proper test configuration
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add bin and utils directories to Python path
bin_dir = project_root / "bin"
utils_dir = project_root / "utils"

if str(bin_dir) not in sys.path:
    sys.path.insert(0, str(bin_dir))

if str(utils_dir) not in sys.path:
    sys.path.insert(0, str(utils_dir))

# Configure test environment
os.environ.setdefault("TEST_MODE", "True")
os.environ.setdefault("MOCK_EXTERNAL_APIS", "True")
"""

        with open(conftest_path, "w") as f:
            f.write(conftest_content)

        logger.info(f"Created conftest.py at {conftest_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating conftest.py: {e}")
        return False


def create_pytest_ini(project_root, verbose=False):
    """
    Create a minimal pytest.ini file for proper test configuration.

    Args:
        project_root (Path): Path to the project root directory
        verbose (bool): Whether to enable verbose logging

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Creating minimal pytest.ini for proper test configuration")

        pytest_ini_path = project_root / "pytest.ini"

        pytest_ini_content = """
[pytest]
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Add project root to Python path
pythonpath = .

# Configure test environment
env =
    TEST_MODE=True
    MOCK_EXTERNAL_APIS=True
"""

        with open(pytest_ini_path, "w") as f:
            f.write(pytest_ini_content)

        logger.info(f"Created pytest.ini at {pytest_ini_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating pytest.ini: {e}")
        return False


def verify_import_resolution(project_root, verbose=False):
    """
    Verify that import resolution works correctly by running a simple test.

    Args:
        project_root (Path): Path to the project root directory
        verbose (bool): Whether to enable verbose logging

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Verifying import resolution with a simple test")

        # Create a simple test file
        test_dir = project_root / "tests" / "verify_imports"
        test_dir.mkdir(exist_ok=True, parents=True)

        test_file_path = test_dir / "test_import_resolution.py"

        test_file_content = """
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

        with open(test_file_path, "w") as f:
            f.write(test_file_content)

        logger.info(f"Created test file at {test_file_path}")

        # Run the test
        logger.info("Running import resolution test")

        cmd = [sys.executable, "-m", "pytest", str(test_file_path), "-v"]

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)

            if verbose:
                logger.info(f"Test output:\n{result.stdout}")
                if result.stderr:
                    logger.info(f"Test errors:\n{result.stderr}")

            if result.returncode == 0:
                logger.info("Import resolution test passed successfully")
                return True
            else:
                logger.error(f"Import resolution test failed with exit code {result.returncode}")
                return False
        except Exception as e:
            logger.error(f"Error running import resolution test: {e}")
            return False

    except Exception as e:
        logger.error(f"Error verifying import resolution: {e}")
        return False


def main():
    """Main function with error handling."""
    try:
        parser = argparse.ArgumentParser(description="Minimal Python Path Fix Script")
        parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

        args = parser.parse_args()

        if args.verbose:
            logger.setLevel(logging.DEBUG)
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)

        # Determine project root
        project_root = Path(__file__).parent.parent

        logger.info(f"Project root: {project_root}")

        # Create .pth file
        pth_success = create_pth_file(project_root, args.verbose)

        if not pth_success:
            logger.warning("Failed to create .pth file, but continuing with other fixes")

        # Create conftest.py
        conftest_success = create_conftest_py(project_root, args.verbose)

        if not conftest_success:
            logger.error("Failed to create conftest.py")
            return 1

        # Create pytest.ini
        pytest_ini_success = create_pytest_ini(project_root, args.verbose)

        if not pytest_ini_success:
            logger.error("Failed to create pytest.ini")
            return 1

        # Verify import resolution
        verify_success = verify_import_resolution(project_root, args.verbose)

        if not verify_success:
            logger.error("Import resolution verification failed")
            return 1

        logger.info("Python path fix completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
