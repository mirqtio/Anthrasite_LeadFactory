import os
import sys
from pathlib import Path

# Add project root to Python path for package imports
project_root = Path(__file__).parent

# Always add project root to sys.path for consistent imports
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add bin directory to Python path (needed for scripts)
bin_dir = project_root / "bin"
if str(bin_dir) not in sys.path:
    sys.path.insert(0, str(bin_dir))

# Configure test environment
os.environ.setdefault("TEST_MODE", "True")
os.environ.setdefault("MOCK_EXTERNAL_APIS", "True")
