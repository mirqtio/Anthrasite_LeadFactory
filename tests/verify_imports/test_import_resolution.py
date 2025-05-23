# Test import resolution
import sys
from pathlib import Path


def test_bin_imports():
    """Test that bin modules can be imported."""
    try:
        # Try to import a module from bin
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        import bin

        assert True
    except ImportError as e:
        raise AssertionError(f"Failed to import bin: {e}")


def test_utils_imports():
    """Test that utils modules can be imported."""
    try:
        # Try to import a module from utils
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        import utils

        assert True
    except ImportError as e:
        raise AssertionError(f"Failed to import utils: {e}")
