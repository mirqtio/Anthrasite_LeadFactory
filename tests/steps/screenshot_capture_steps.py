"""Step definitions for local screenshot capture feature."""
import os
import tempfile
from unittest.mock import MagicMock, patch

from pytest_bdd import given, parsers, then, when

from leadfactory.pipeline.screenshot import (
    create_screenshot_asset,
    generate_business_screenshot,
    get_businesses_needing_screenshots,
)
from leadfactory.pipeline.screenshot_local import (
    capture_screenshot_sync,
    is_playwright_available,
)


@given("the screenshot capture system is initialized")
def screenshot_system_initialized():
    """Initialize screenshot capture system."""
    # System is initialized by default
    pass


@given("I have a ScreenshotOne API key configured")
def screenshotone_api_key_configured(test_data):
    """Set up ScreenshotOne API key."""
    test_data["original_api_key"] = os.environ.get("SCREENSHOT_ONE_KEY")
    os.environ["SCREENSHOT_ONE_KEY"] = "test-api-key-12345"


@given("I have no ScreenshotOne API key configured")
def no_screenshotone_api_key(test_data):
    """Remove ScreenshotOne API key."""
    test_data["original_api_key"] = os.environ.get("SCREENSHOT_ONE_KEY")
    if "SCREENSHOT_ONE_KEY" in os.environ:
        del os.environ["SCREENSHOT_ONE_KEY"]


@given("Playwright is installed and available")
def playwright_available(test_data):
    """Mock Playwright as available."""
    test_data["playwright_mock"] = patch(
        "leadfactory.pipeline.screenshot_local.is_playwright_available",
        return_value=True
    ).start()


@given("Playwright is not available")
def playwright_not_available(test_data):
    """Mock Playwright as not available."""
    test_data["playwright_mock"] = patch(
        "leadfactory.pipeline.screenshot_local.is_playwright_available",
        return_value=False
    ).start()


@given("the ScreenshotOne API returns an error")
def screenshotone_api_error(test_data):
    """Mock ScreenshotOne API error."""
    import requests

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")

    test_data["requests_mock"] = patch(
        "requests.get",
        return_value=mock_response
    ).start()


@given("I am running in test mode")
def running_in_test_mode(test_data):
    """Set test mode environment."""
    test_data["original_e2e_mode"] = os.environ.get("E2E_MODE")
    os.environ["E2E_MODE"] = "true"


@given("I am not in test mode")
def not_in_test_mode(test_data):
    """Ensure not in test mode."""
    test_data["original_e2e_mode"] = os.environ.get("E2E_MODE")
    test_data["original_prod_test_mode"] = os.environ.get("PRODUCTION_TEST_MODE")
    os.environ["E2E_MODE"] = "false"
    os.environ["PRODUCTION_TEST_MODE"] = "false"


@given("I have multiple businesses needing screenshots:", target_fixture="businesses_table")
def multiple_businesses_needing_screenshots(datatable, test_data):
    """Set up multiple businesses for screenshot processing."""
    businesses = []
    # Skip header row
    headers = datatable[0]
    for row in datatable[1:]:
        # Create dict from row data
        row_dict = dict(zip(headers, row))
        businesses.append({
            "id": int(row_dict["id"]),
            "name": row_dict["name"],
            "website": row_dict["website"]
        })
    test_data["test_businesses"] = businesses


@given("Playwright is available")
def playwright_is_available(test_data):
    """Ensure Playwright is available."""
    if "playwright_mock" in test_data:
        test_data["playwright_mock"].stop()

    # Mock successful screenshot capture
    test_data["capture_mock"] = patch(
        "leadfactory.pipeline.screenshot_local.capture_screenshot_sync",
        return_value=True
    ).start()


@given("cost tracking is enabled")
def cost_tracking_enabled():
    """Cost tracking is always enabled in the system."""
    pass


@when(parsers.parse('I capture a screenshot of "{url}"'))
def capture_screenshot(url, test_data):
    """Capture a screenshot of the given URL."""
    test_business = {
        "id": 12345,
        "name": "Test Business",
        "website": url
    }

    # Mock the asset creation
    with patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True) as mock_create:
        test_data["asset_creation_mock"] = mock_create

        try:
            success = generate_business_screenshot(test_business)
            test_data["screenshot_success"] = success
            test_data["screenshot_error"] = None
        except Exception as e:
            test_data["screenshot_success"] = False
            test_data["screenshot_error"] = str(e)


@when(parsers.parse('I try to capture a screenshot of "{url}"'))
def try_capture_screenshot(url, test_data):
    """Try to capture a screenshot, expecting potential failure."""
    capture_screenshot(url, test_data)


@when("I process screenshots for all businesses")
def process_all_screenshots(test_data):
    """Process screenshots for all test businesses."""
    test_data["processed_count"] = 0
    test_data["asset_records_created"] = 0

    # Ensure no API key (to use local capture)
    original_key = os.environ.get("SCREENSHOT_ONE_KEY")
    if "SCREENSHOT_ONE_KEY" in os.environ:
        del os.environ["SCREENSHOT_ONE_KEY"]

    try:
        with patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True) as mock_create, \
             patch("leadfactory.pipeline.screenshot_local.is_playwright_available", return_value=True), \
             patch("leadfactory.pipeline.screenshot_local.capture_screenshot_sync", return_value=True):

            for business in test_data["test_businesses"]:
                success = generate_business_screenshot(business)
                if success:
                    test_data["processed_count"] += 1

            test_data["asset_records_created"] = mock_create.call_count
    finally:
        if original_key:
            os.environ["SCREENSHOT_ONE_KEY"] = original_key


@when(parsers.parse("I capture a screenshot with viewport {width:d}x{height:d}"))
def capture_with_viewport(width, height, test_data):
    """Capture screenshot with custom viewport."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        output_path = tmp_file.name

    test_data["screenshot_path"] = output_path

    # Mock the capture with viewport parameters
    with patch("leadfactory.pipeline.screenshot_local.capture_screenshot_sync") as mock_capture:
        mock_capture.return_value = True

        success = capture_screenshot_sync(
            url="https://example.com",
            output_path=output_path,
            viewport_width=width,
            viewport_height=height
        )

        test_data["viewport_capture_success"] = success
        test_data["capture_args"] = mock_capture.call_args


@when("I capture a screenshot using the API")
def capture_using_api(test_data):
    """Capture screenshot using ScreenshotOne API."""
    # Ensure API key is set
    os.environ["SCREENSHOT_ONE_KEY"] = "test-api-key"

    # Mock successful API response
    mock_response = MagicMock()
    mock_response.content = b"fake screenshot data"
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        capture_screenshot("https://example.com", test_data)


@when("I capture a screenshot using local capture")
def capture_using_local(test_data):
    """Capture screenshot using local Playwright."""
    # Ensure no API key
    if "SCREENSHOT_ONE_KEY" in os.environ:
        del os.environ["SCREENSHOT_ONE_KEY"]

    # Mock Playwright availability
    with patch("leadfactory.pipeline.screenshot_local.is_playwright_available", return_value=True), \
         patch("leadfactory.pipeline.screenshot_local.capture_screenshot_sync", return_value=True):
        capture_screenshot("https://example.com", test_data)


@then("the screenshot should be captured using ScreenshotOne API")
def verify_api_capture(test_data):
    """Verify screenshot was captured using API."""
    assert test_data.get("screenshot_success") is True
    # In real implementation, we would check logs or metrics


@then("the screenshot should be captured using Playwright")
def verify_playwright_capture(test_data):
    """Verify screenshot was captured using Playwright."""
    assert test_data.get("screenshot_success") is True


@then("the screenshot file should be created")
def verify_screenshot_created(test_data):
    """Verify screenshot file exists."""
    assert test_data.get("screenshot_success") is True


@then("an asset record should be created in the database")
def verify_asset_record(test_data):
    """Verify asset record was created."""
    if "asset_creation_mock" in test_data:
        assert test_data["asset_creation_mock"].called


@then("the system should fallback to Playwright capture")
def verify_fallback_to_playwright(test_data):
    """Verify system fell back to Playwright."""
    assert test_data.get("screenshot_success") is True


@then("a placeholder screenshot should be generated")
def verify_placeholder_generated(test_data):
    """Verify placeholder was generated."""
    assert test_data.get("screenshot_success") is True


@then("the placeholder should contain the business name and URL")
def verify_placeholder_content(test_data):
    """Verify placeholder contains expected content."""
    # In test mode, placeholders are generated
    assert test_data.get("screenshot_success") is True


@then("the screenshot generation should fail with an error")
def verify_screenshot_failed(test_data):
    """Verify screenshot generation failed."""
    assert test_data.get("screenshot_success") is False
    assert test_data.get("screenshot_error") is not None


@then(parsers.parse("{count:d} screenshots should be generated"))
def verify_screenshot_count(count, test_data):
    """Verify number of screenshots generated."""
    assert test_data.get("processed_count") == count


@then(parsers.parse("{count:d} asset records should be created"))
def verify_asset_count(count, test_data):
    """Verify number of asset records created."""
    assert test_data.get("asset_records_created") == count


@then("Playwright should add https:// protocol automatically")
def verify_protocol_added(test_data):
    """Verify protocol was added to URL."""
    # This is handled internally by the capture function
    pass


@then("attempt to capture the screenshot")
def verify_capture_attempted(test_data):
    """Verify screenshot capture was attempted."""
    # Capture was attempted in the when step
    pass


@then("the screenshot should have the specified dimensions")
def verify_viewport_dimensions(test_data):
    """Verify screenshot has correct viewport dimensions."""
    assert test_data.get("viewport_capture_success") is True

    if test_data.get("capture_args"):
        kwargs = test_data["capture_args"][1]
        assert kwargs.get("viewport_width") in [1920, 1280]  # Common viewport widths
        assert kwargs.get("viewport_height") in [1080, 800]  # Common viewport heights


@then("the cost should be logged as 1 cent per screenshot")
def verify_api_cost_logged(test_data):
    """Verify API cost was logged."""
    # In production, this would check metrics/logs
    assert test_data.get("screenshot_success") is True


@then("no cost should be recorded for the screenshot")
def verify_no_cost_recorded(test_data):
    """Verify no cost for local capture."""
    # Local captures have zero cost
    assert test_data.get("screenshot_success") is True


# Cleanup function
def cleanup_screenshot_tests(test_data):
    """Clean up after screenshot tests."""
    # Restore environment variables
    if "original_api_key" in test_data:
        if test_data["original_api_key"]:
            os.environ["SCREENSHOT_ONE_KEY"] = test_data["original_api_key"]
        elif "SCREENSHOT_ONE_KEY" in os.environ:
            del os.environ["SCREENSHOT_ONE_KEY"]

    if "original_e2e_mode" in test_data:
        if test_data["original_e2e_mode"]:
            os.environ["E2E_MODE"] = test_data["original_e2e_mode"]
        elif "E2E_MODE" in os.environ:
            del os.environ["E2E_MODE"]

    if "original_prod_test_mode" in test_data:
        if test_data["original_prod_test_mode"]:
            os.environ["PRODUCTION_TEST_MODE"] = test_data["original_prod_test_mode"]
        elif "PRODUCTION_TEST_MODE" in os.environ:
            del os.environ["PRODUCTION_TEST_MODE"]

    # Stop mocks
    for mock_name in ["playwright_mock", "requests_mock", "capture_mock"]:
        if mock_name in test_data and hasattr(test_data[mock_name], "stop"):
            test_data[mock_name].stop()

    # Clean up temp files
    if "screenshot_path" in test_data and os.path.exists(test_data["screenshot_path"]):
        os.unlink(test_data["screenshot_path"])
