"""
API Test Fixtures

This module provides test fixtures for both real and mock API services used in integration tests.
Each fixture checks the test configuration to determine whether to use a real API or a mock.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock

import pytest

from tests.integration.api_test_config import APITestConfig, api_call_metrics

# Mock response data directory
MOCK_DATA_DIR = Path(__file__).parent / "mock_data"
MOCK_DATA_DIR.mkdir(exist_ok=True)


# Yelp API fixtures
@pytest.fixture
def yelp_api(api_metrics_logger):
    """
    Fixture for Yelp Fusion API that toggles between real and mock implementation.
    """
    if APITestConfig.should_use_real_api("yelp"):
        # Import the real client
        try:
            import requests

            class RealYelpAPI:
                def __init__(self):
                    self.api_key = os.environ.get("YELP_API_KEY")
                    self.base_url = "https://api.yelp.com/v3"
                    self.headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "application/json",
                    }

                @api_call_metrics("yelp", "business_search")
                def business_search(self, term: str, location: str, **kwargs) -> dict[str, Any]:
                    """Search for businesses on Yelp."""
                    url = f"{self.base_url}/businesses/search"
                    params = {"term": term, "location": location, **kwargs}
                    response = requests.get(url, headers=self.headers, params=params)
                    response.raise_for_status()
                    return response.json()

                @api_call_metrics("yelp", "business_details")
                def business_details(self, business_id: str) -> dict[str, Any]:
                    """Get details for a specific business on Yelp."""
                    url = f"{self.base_url}/businesses/{business_id}"
                    response = requests.get(url, headers=self.headers)
                    response.raise_for_status()
                    return response.json()

            return RealYelpAPI()
        except (ImportError, Exception):
            pass

    # Use mock implementation
    mock_yelp = MagicMock()

    # Set up mock business_search method
    def mock_business_search(term: str, location: str, **kwargs) -> dict[str, Any]:
        mock_file = MOCK_DATA_DIR / "yelp_business_search.json"
        if mock_file.exists():
            with open(mock_file) as f:
                return json.load(f)
        return {
            "businesses": [
                {
                    "id": "mock-business-1",
                    "name": "Mock Business 1",
                    "url": "https://yelp.com/biz/mock-business-1",
                    "review_count": 42,
                    "rating": 4.5,
                    "location": {"address1": "123 Main St", "city": "Mockville", "state": "NY", "zip_code": "10002"},
                    "phone": "+15551234567",
                    "categories": [{"alias": "plumbers", "title": "Plumbers"}],
                }
            ],
            "total": 1,
        }

    # Set up mock business_details method
    def mock_business_details(business_id: str) -> dict[str, Any]:
        mock_file = MOCK_DATA_DIR / f"yelp_business_{business_id}.json"
        if mock_file.exists():
            with open(mock_file) as f:
                return json.load(f)
        return {
            "id": business_id,
            "name": f"Mock Business {business_id}",
            "url": f"https://yelp.com/biz/{business_id}",
            "review_count": 42,
            "rating": 4.5,
            "location": {"address1": "123 Main St", "city": "Mockville", "state": "NY", "zip_code": "10002"},
            "phone": "+15551234567",
            "categories": [{"alias": "plumbers", "title": "Plumbers"}],
            "hours": [{"open": [{"day": 0, "start": "0900", "end": "1700"}]}],
            "price": "$$",
        }

    mock_yelp.business_search.side_effect = mock_business_search
    mock_yelp.business_details.side_effect = mock_business_details

    return mock_yelp


# Google Places API fixtures
@pytest.fixture
def google_places_api(api_metrics_logger):
    """
    Fixture for Google Places API that toggles between real and mock implementation.
    """
    if APITestConfig.should_use_real_api("google"):
        # Import the real client
        try:
            import requests

            class RealGooglePlacesAPI:
                def __init__(self):
                    self.api_key = os.environ.get("GOOGLE_API_KEY")
                    self.base_url = "https://maps.googleapis.com/maps/api/place"

                @api_call_metrics("google", "place_search")
                def place_search(self, query: str, **kwargs) -> dict[str, Any]:
                    """Search for places using Google Places API."""
                    url = f"{self.base_url}/textsearch/json"
                    params = {"query": query, "key": self.api_key, **kwargs}
                    response = requests.get(url, params=params)
                    response.raise_for_status()
                    return response.json()

                @api_call_metrics("google", "place_details")
                def place_details(self, place_id: str) -> dict[str, Any]:
                    """Get details for a specific place using Google Places API."""
                    url = f"{self.base_url}/details/json"
                    params = {"place_id": place_id, "key": self.api_key, "fields": "name,formatted_address,formatted_phone_number,website,url,rating,user_ratings_total,opening_hours"}
                    response = requests.get(url, params=params)
                    response.raise_for_status()
                    return response.json()

            return RealGooglePlacesAPI()
        except (ImportError, Exception):
            pass

    # Use mock implementation
    mock_google = MagicMock()

    # Set up mock place_search method
    def mock_place_search(query: str, **kwargs) -> dict[str, Any]:
        mock_file = MOCK_DATA_DIR / "google_place_search.json"
        if mock_file.exists():
            with open(mock_file) as f:
                return json.load(f)
        return {
            "results": [
                {
                    "place_id": "mock-place-1",
                    "name": "Mock Place 1",
                    "formatted_address": "123 Main St, Mockville, NY 10002",
                    "rating": 4.5,
                    "user_ratings_total": 42,
                }
            ],
            "status": "OK",
        }

    # Set up mock place_details method
    def mock_place_details(place_id: str) -> dict[str, Any]:
        mock_file = MOCK_DATA_DIR / f"google_place_{place_id}.json"
        if mock_file.exists():
            with open(mock_file) as f:
                return json.load(f)
        return {
            "result": {
                "place_id": place_id,
                "name": f"Mock Place {place_id}",
                "formatted_address": "123 Main St, Mockville, NY 10002",
                "formatted_phone_number": "+1 (555) 123-4567",
                "website": "https://example.com",
                "url": f"https://maps.google.com/?cid={place_id}",
                "rating": 4.5,
                "user_ratings_total": 42,
                "opening_hours": {
                    "weekday_text": [
                        "Monday: 9:00 AM – 5:00 PM",
                        "Tuesday: 9:00 AM – 5:00 PM",
                        "Wednesday: 9:00 AM – 5:00 PM",
                        "Thursday: 9:00 AM – 5:00 PM",
                        "Friday: 9:00 AM – 5:00 PM",
                        "Saturday: Closed",
                        "Sunday: Closed"
                    ]
                },
            },
            "status": "OK",
        }

    mock_google.place_search.side_effect = mock_place_search
    mock_google.place_details.side_effect = mock_place_details

    return mock_google


# OpenAI API fixtures
@pytest.fixture
def openai_api(api_metrics_logger):
    """
    Fixture for OpenAI API that toggles between real and mock implementation.
    """
    if APITestConfig.should_use_real_api("openai"):
        # Import the real client
        try:
            from openai import OpenAI

            class RealOpenAIAPI:
                def __init__(self):
                    self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

                @api_call_metrics("openai", "chat_completion")
                def chat_completion(self, messages: list[dict[str, str]], model: str = "gpt-4o", **kwargs) -> dict[str, Any]:
                    """Generate a chat completion using OpenAI API."""
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        **kwargs
                    )
                    # Convert to dict for consistent return type
                    return response.model_dump()

            return RealOpenAIAPI()
        except (ImportError, Exception):
            pass

    # Use mock implementation
    mock_openai = MagicMock()

    # Set up mock chat_completion method
    def mock_chat_completion(messages: list[dict[str, str]], model: str = "gpt-4o", **kwargs) -> dict[str, Any]:
        mock_file = MOCK_DATA_DIR / "openai_chat_completion.json"
        if mock_file.exists():
            with open(mock_file) as f:
                return json.load(f)

        # Extract the last user message for the mock response
        last_message = messages[-1].get("content", "") if messages else ""
        mock_response = {
            "id": "mock-completion-id",
            "object": "chat.completion",
            "created": 1716585600,  # May 25, 2024
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"This is a mock response to: {last_message[:50]}..."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(" ".join([m.get("content", "") for m in messages]).split()),
                "completion_tokens": 20,
                "total_tokens": len(" ".join([m.get("content", "") for m in messages]).split()) + 20
            }
        }
        return mock_response

    mock_openai.chat_completion.side_effect = mock_chat_completion

    return mock_openai


# SendGrid API fixtures
@pytest.fixture
def sendgrid_api(api_metrics_logger):
    """
    Fixture for SendGrid API that toggles between real and mock implementation.
    """
    if APITestConfig.should_use_real_api("sendgrid"):
        # Import the real client
        try:
            import sendgrid
            from sendgrid.helpers.mail import Content, Email, Mail, To

            class RealSendGridAPI:
                def __init__(self):
                    self.client = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))

                @api_call_metrics("sendgrid", "send_email")
                def send_email(self, from_email: str, to_email: str, subject: str, content: str, **kwargs) -> dict[str, Any]:
                    """Send an email using SendGrid API."""
                    message = Mail(
                        from_email=Email(from_email),
                        to_emails=To(to_email),
                        subject=subject,
                        html_content=Content("text/html", content)
                    )

                    response = self.client.send(message)
                    return {
                        "status_code": response.status_code,
                        "body": response.body.decode("utf-8") if response.body else "",
                        "headers": dict(response.headers),
                    }

            return RealSendGridAPI()
        except (ImportError, Exception):
            pass

    # Use mock implementation
    mock_sendgrid = MagicMock()

    # Set up mock send_email method
    def mock_send_email(from_email: str, to_email: str, subject: str, content: str, **kwargs) -> dict[str, Any]:
        return {
            "status_code": 202,  # Standard successful response from SendGrid
            "body": "",
            "headers": {
                "x-message-id": "mock-message-id-12345",
                "server": "SendGrid",
                "date": "Sat, 25 May 2024 11:00:00 +0000",
            },
        }

    mock_sendgrid.send_email.side_effect = mock_send_email

    return mock_sendgrid


# ScreenshotOne API fixtures
@pytest.fixture
def screenshotone_api(api_metrics_logger):
    """
    Fixture for ScreenshotOne API that toggles between real and mock implementation.
    """
    if APITestConfig.should_use_real_api("screenshotone"):
        # Import the real client
        try:
            import requests

            class RealScreenshotOneAPI:
                def __init__(self):
                    self.api_key = os.environ.get("SCREENSHOTONE_API_KEY")
                    self.base_url = "https://api.screenshotone.com"

                @api_call_metrics("screenshotone", "take_screenshot")
                def take_screenshot(self, url: str, **kwargs) -> bytes:
                    """Take a screenshot of a webpage using ScreenshotOne API."""
                    api_url = f"{self.base_url}/take"
                    params = {
                        "access_key": self.api_key,
                        "url": url,
                        "device_scale_factor": kwargs.get("device_scale_factor", 1),
                        "format": kwargs.get("format", "png"),
                        "full_page": kwargs.get("full_page", True),
                        "width": kwargs.get("width", 1280),
                        "height": kwargs.get("height", 800),
                    }
                    response = requests.get(api_url, params=params)
                    response.raise_for_status()
                    return response.content

            return RealScreenshotOneAPI()
        except (ImportError, Exception):
            pass

    # Use mock implementation
    mock_screenshotone = MagicMock()

    # Set up mock take_screenshot method
    def mock_take_screenshot(url: str, **kwargs) -> bytes:
        mock_file = MOCK_DATA_DIR / "mock_screenshot.png"
        if mock_file.exists():
            with open(mock_file, "rb") as f:
                return f.read()

        # Generate a simple 1x1 transparent PNG if no mock file exists
        return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

    mock_screenshotone.take_screenshot.side_effect = mock_take_screenshot

    return mock_screenshotone


# Create a directory for mock data if it doesn't exist
@pytest.fixture(scope="session", autouse=True)
def setup_mock_data_dir():
    """Set up mock data directory with example files."""
    MOCK_DATA_DIR.mkdir(exist_ok=True)

    # Check if we need to create example mock data files
    if not (MOCK_DATA_DIR / "example_created.txt").exists():
        # Create example mock data for Yelp
        with open(MOCK_DATA_DIR / "yelp_business_search.json", "w") as f:
            json.dump({
                "businesses": [
                    {
                        "id": "example-business-1",
                        "name": "Example Business 1",
                        "url": "https://yelp.com/biz/example-business-1",
                        "review_count": 42,
                        "rating": 4.5,
                        "location": {"address1": "123 Main St", "city": "Exampleville", "state": "NY", "zip_code": "10002"},
                        "phone": "+15551234567",
                        "categories": [{"alias": "plumbers", "title": "Plumbers"}],
                    }
                ],
                "total": 1,
            }, f, indent=2)

        # Create example mock data for Google Places
        with open(MOCK_DATA_DIR / "google_place_search.json", "w") as f:
            json.dump({
                "results": [
                    {
                        "place_id": "example-place-1",
                        "name": "Example Place 1",
                        "formatted_address": "123 Main St, Exampleville, NY 10002",
                        "rating": 4.5,
                        "user_ratings_total": 42,
                    }
                ],
                "status": "OK",
            }, f, indent=2)

        # Create marker file
        with open(MOCK_DATA_DIR / "example_created.txt", "w") as f:
            f.write("Example mock data files created on 2024-05-25")
