"""BDD test file for screenshot capture feature."""
import pytest
from pytest_bdd import scenarios

# Import step definitions
from tests.steps.screenshot_capture_steps import *


@pytest.fixture
def test_data():
    """Provide test data storage for BDD scenarios."""
    data = {}
    yield data
    # Cleanup after test
    cleanup_screenshot_tests(data)


# Load all scenarios from the feature file
scenarios("features/screenshot_capture.feature")
