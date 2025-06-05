# Local Screenshot Capture

## Overview

The LeadFactory system now supports local screenshot capture using Playwright as a fallback to the ScreenshotOne API. This provides:

- **Cost savings**: No per-screenshot charges when using local capture
- **Reliability**: Fallback option when external API is unavailable
- **Development flexibility**: No API key required for development/testing

## Architecture

The screenshot system uses a hierarchical approach:

1. **Primary**: ScreenshotOne API (if `SCREENSHOT_ONE_KEY` is configured)
2. **Fallback**: Local Playwright capture (if Playwright is installed)
3. **Test Mode**: Placeholder generation (in E2E or test environments)

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs Playwright and Pillow (for placeholder generation).

### 2. Install Playwright Browsers

Run the installation script:

```bash
python scripts/install_playwright.py
```

Or manually install:

```bash
# Install Chromium browser
python -m playwright install chromium

# Install system dependencies (may require sudo)
python -m playwright install-deps chromium
```

## Configuration

### Environment Variables

- `SCREENSHOT_ONE_KEY`: ScreenshotOne API key (optional)
- `E2E_MODE`: Set to "true" to enable placeholder generation
- `PRODUCTION_TEST_MODE`: Set to "true" for production testing with placeholders

### Fallback Behavior

1. If `SCREENSHOT_ONE_KEY` is set:
   - Uses ScreenshotOne API
   - Falls back to Playwright if API fails
   
2. If no API key:
   - Uses Playwright if available
   - Uses placeholders in test modes
   - Fails in production without Playwright

## Usage

### Command Line

```bash
# Process all businesses needing screenshots
python -m leadfactory.pipeline.screenshot

# Process specific business
python -m leadfactory.pipeline.screenshot --id 123

# Limit number of businesses
python -m leadfactory.pipeline.screenshot --limit 10
```

### Python API

```python
from leadfactory.pipeline.screenshot import generate_business_screenshot

# Generate screenshot for a business
business = {
    "id": 123,
    "name": "Example Business",
    "website": "https://example.com"
}

success = generate_business_screenshot(business)
```

### Local Capture Module

```python
from leadfactory.pipeline.screenshot_local import capture_screenshot_sync

# Capture screenshot directly
success = capture_screenshot_sync(
    url="https://example.com",
    output_path="/tmp/screenshot.png",
    viewport_width=1280,
    viewport_height=800,
    full_page=False,
    timeout=30000
)
```

## Cost Comparison

| Method | Cost per Screenshot | Notes |
|--------|-------------------|-------|
| ScreenshotOne API | $0.01 | Reliable, fast, cloud-based |
| Local Playwright | $0.00 | Free, requires local resources |
| Placeholder | $0.00 | Test mode only |

### Monthly Cost Examples

- 1,000 screenshots/month:
  - API: $10.00
  - Local: $0.00
  
- 10,000 screenshots/month:
  - API: $100.00
  - Local: $0.00

## Performance Considerations

### Local Capture Performance

- **Memory**: ~200-500MB per browser instance
- **CPU**: Moderate usage during page rendering
- **Time**: 2-10 seconds per screenshot (depends on site)

### Optimization Tips

1. **Reuse browser instances** when processing batches
2. **Set appropriate timeouts** to avoid hanging on slow sites
3. **Use headless mode** (default) for better performance
4. **Limit concurrent captures** to avoid resource exhaustion

## Troubleshooting

### Common Issues

1. **"Playwright not installed"**
   ```bash
   pip install playwright
   python -m playwright install chromium
   ```

2. **"Browser executable not found"**
   ```bash
   python scripts/install_playwright.py
   ```

3. **"Permission denied" on Linux**
   ```bash
   sudo python -m playwright install-deps chromium
   ```

4. **Timeout errors**
   - Increase timeout in capture_screenshot_sync()
   - Check if website is accessible
   - Verify network connectivity

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('leadfactory.pipeline.screenshot_local').setLevel(logging.DEBUG)
```

## Security Considerations

1. **Sandbox Mode**: Chromium runs with sandbox disabled in containers
2. **User Agent**: Set to appear as regular browser
3. **Cookies**: Not persisted between captures
4. **JavaScript**: Enabled by default (required for many sites)

## Docker Support

For containerized environments, use our Docker image with Playwright pre-installed:

```dockerfile
FROM python:3.9-slim

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    xdg-utils

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install chromium
```

## Best Practices

1. **Use API in production** for reliability and performance
2. **Use local capture in development** to save costs
3. **Monitor resource usage** when using local capture at scale
4. **Implement retry logic** for both methods
5. **Cache screenshots** to avoid redundant captures
6. **Set appropriate viewport sizes** based on your needs

## Future Enhancements

- [ ] Support for mobile viewport presets
- [ ] Parallel capture for batch processing
- [ ] Screenshot comparison/diff functionality
- [ ] WebP format support for smaller files
- [ ] Integration with CDN for screenshot hosting