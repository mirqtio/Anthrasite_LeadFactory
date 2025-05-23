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
