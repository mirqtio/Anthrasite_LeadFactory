import os
import sys
from pathlib import Path

# TEMPORARILY DISABLED: sys.path modifications to test package imports
# Only add project root to Python path for non-integration tests
# Integration tests should use the installed package
project_root = Path(__file__).parent
is_integration_test = any("integration" in arg for arg in sys.argv)

# DISABLED: Commenting out sys.path modifications to test package imports
# if not is_integration_test and str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))

# Add bin and utils directories to Python path (needed for legacy scripts)
bin_dir = project_root / "bin"
utils_dir = project_root / "utils"

# DISABLED: Commenting out sys.path modifications to test package imports
# if str(bin_dir) not in sys.path:
#     sys.path.insert(0, str(bin_dir))

# if str(utils_dir) not in sys.path:
#     sys.path.insert(0, str(utils_dir))

# Configure test environment
os.environ.setdefault("TEST_MODE", "True")
os.environ.setdefault("MOCK_EXTERNAL_APIS", "True")
