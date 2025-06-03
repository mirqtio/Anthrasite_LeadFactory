import os
import sys
from pathlib import Path

# Add project root to Python path for package imports
project_root = Path(__file__).parent
is_integration_test = any("integration" in arg for arg in sys.argv)

# For tests, we want to use the installed package, not the local directory
# Only add project root if the package is not already installed
try:
    import leadfactory

    # If import succeeds, check if it's the installed package
    leadfactory_path = Path(leadfactory.__file__).parent
    if str(project_root / "leadfactory") in str(leadfactory_path):
        # It's using the local directory, we need to prioritize installed package
        # Remove project root from sys.path if it's there
        if str(project_root) in sys.path:
            sys.path.remove(str(project_root))
except ImportError:
    # Package not installed, add project root to sys.path for development
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# Add bin and utils directories to Python path (needed for legacy scripts)
bin_dir = project_root / "bin"
utils_dir = project_root / "utils"

# Add bin and utils to sys.path
if str(bin_dir) not in sys.path:
    sys.path.insert(0, str(bin_dir))

if str(utils_dir) not in sys.path:
    sys.path.insert(0, str(utils_dir))

# Configure test environment
os.environ.setdefault("TEST_MODE", "True")
os.environ.setdefault("MOCK_EXTERNAL_APIS", "True")
