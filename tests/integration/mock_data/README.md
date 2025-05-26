# Mock Data for API Integration Tests

This directory contains mock data files used for API integration tests. These files provide consistent test data that can be used when real API connections are not available or desired.

## Mock Data Files

### Yelp API
- `yelp_business_search.json` - Mock response for Yelp business search
- `yelp_business_mock-business-1.json` - Mock response for a specific business details

### Google Places API
- `google_place_search.json` - Mock response for Google Places search
- `google_place_mock-place-1.json` - Mock response for a specific place details

### OpenAI API
- `openai_chat_completion.json` - Mock response for OpenAI chat completion

### ScreenshotOne API
- `mock_screenshot.png` - Mock screenshot image

## Updating Mock Data

To update or add new mock data:

1. For JSON files, ensure they match the structure of actual API responses
2. To regenerate the mock screenshot, run `python3 generate_mock_screenshot.py`
3. Add any new mock files to this README for documentation purposes

## Testing with Mock Data

By default, tests use these mock files. To use real API calls instead, run tests with:

```bash
pytest --use-real-apis
```

Or to test specific APIs with real calls:

```bash
pytest --use-real-apis --apis=yelp,google
```
