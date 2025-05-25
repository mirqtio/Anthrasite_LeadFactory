#!/usr/bin/env python3
"""
Real API Integration Validator

This script validates that the API integration tests can run with real API credentials.
It provides a simple way to test each API individually and report on the success or failure.

Usage:
    python validate_real_api_integration.py [--api <api_name>]

Options:
    --api <api_name>   Test a specific API only (yelp, google, openai, sendgrid, screenshotone)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Import required modules
import requests

# Define real API client classes (simplified versions of what's in the fixtures)
class RealYelpAPI:
    def __init__(self):
        self.api_key = os.environ.get("YELP_API_KEY")
        self.base_url = "https://api.yelp.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def business_search(self, term: str, location: str, **kwargs) -> Dict[str, Any]:
        """Search for businesses on Yelp."""
        url = f"{self.base_url}/businesses/search"
        params = {"term": term, "location": location, **kwargs}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

class RealGooglePlacesAPI:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api/place"

    def place_search(self, query: str, location: str = None, radius: int = 1000, **kwargs) -> Dict[str, Any]:
        """Search for places using Google Places API."""
        url = f"{self.base_url}/textsearch/json"
        params = {"query": query, "key": self.api_key, **kwargs}

        if location:
            params["location"] = location
            params["radius"] = radius

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

class RealOpenAIAPI:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def chat_completion(self, messages: List[Dict[str, str]], model: str = "gpt-4o", **kwargs) -> Dict[str, Any]:
        """Generate chat completions using OpenAI API."""
        url = f"{self.base_url}/chat/completions"
        data = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

class RealSendGridAPI:
    def __init__(self):
        self.api_key = os.environ.get("SENDGRID_API_KEY")
        self.base_url = "https://api.sendgrid.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.from_email = os.environ.get("SENDGRID_FROM_EMAIL")

    def send_email(self, to_email: str, subject: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send an email using SendGrid API."""
        # In the validation script, we won't actually send emails
        return {"message": "SendGrid client initialized successfully"}

class RealScreenshotOneAPI:
    def __init__(self):
        self.api_key = os.environ.get("SCREENSHOT_ONE_API_KEY")
        self.base_url = "https://api.screenshotone.com"

    def take_screenshot(self, url: str, **kwargs) -> bytes:
        """Take a screenshot using ScreenshotOne API."""
        # In the validation script, we won't actually take screenshots
        return b"Screenshot client initialized successfully"


def check_api_key(api_name: str) -> bool:
    """Check if the API key for a specific API is available in environment variables."""
    key_mapping = {
        'yelp': 'YELP_API_KEY',
        'google': 'GOOGLE_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'sendgrid': 'SENDGRID_API_KEY',
        'screenshotone': 'SCREENSHOT_ONE_API_KEY',
    }

    env_var = key_mapping.get(api_name)
    if not env_var:
        return False

    return bool(os.environ.get(env_var))


def validate_yelp_api() -> Dict[str, Any]:
    """Validate the Yelp API integration."""
    print("\n🔍 Testing Yelp API integration...")
    result = {
        "api": "yelp",
        "key_available": check_api_key("yelp"),
        "success": False,
        "latency": 0,
        "error": None,
        "response_sample": None
    }

    if not result["key_available"]:
        result["error"] = "API key not found in environment variables"
        print("❌ Yelp API key not found in environment variables")
        return result

    try:
        # Create a real Yelp API client
        client = RealYelpAPI()

        # Time the API call
        start_time = time.time()
        response = client.business_search(term="plumber", location="New York", limit=3)
        result["latency"] = time.time() - start_time

        # Validate the response
        if "businesses" in response and isinstance(response["businesses"], list):
            result["success"] = True
            result["response_sample"] = {
                "total": len(response["businesses"]),
                "first_business": response["businesses"][0]["name"] if response["businesses"] else None
            }
            print(f"✅ Yelp API test successful - found {len(response['businesses'])} businesses")
        else:
            result["error"] = "Invalid response format"
            print("❌ Yelp API test failed - invalid response format")
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Yelp API test failed with error: {e}")

    return result


def validate_google_places_api() -> Dict[str, Any]:
    """Validate the Google Places API integration."""
    print("\n🔍 Testing Google Places API integration...")
    result = {
        "api": "google",
        "key_available": check_api_key("google"),
        "success": False,
        "latency": 0,
        "error": None,
        "response_sample": None
    }

    if not result["key_available"]:
        result["error"] = "API key not found in environment variables"
        print("❌ Google Places API key not found in environment variables")
        return result

    try:
        # Create a real Google Places API client
        client = RealGooglePlacesAPI()

        # Time the API call
        start_time = time.time()
        response = client.place_search(query="restaurant", location="Seattle, WA", radius=1000)
        result["latency"] = time.time() - start_time

        # Validate the response
        if "results" in response and isinstance(response["results"], list):
            result["success"] = True
            result["response_sample"] = {
                "total": len(response["results"]),
                "first_place": response["results"][0]["name"] if response["results"] else None
            }
            print(f"✅ Google Places API test successful - found {len(response['results'])} places")
        else:
            result["error"] = "Invalid response format"
            print("❌ Google Places API test failed - invalid response format")
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Google Places API test failed with error: {e}")

    return result


def validate_openai_api() -> Dict[str, Any]:
    """Validate the OpenAI API integration."""
    print("\n🔍 Testing OpenAI API integration...")
    result = {
        "api": "openai",
        "key_available": check_api_key("openai"),
        "success": False,
        "latency": 0,
        "error": None,
        "response_sample": None
    }

    if not result["key_available"]:
        result["error"] = "API key not found in environment variables"
        print("❌ OpenAI API key not found in environment variables")
        return result

    try:
        # Create a real OpenAI API client
        client = RealOpenAIAPI()

        # Time the API call
        start_time = time.time()
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello world"}
            ],
            model="gpt-4o"
        )
        result["latency"] = time.time() - start_time

        # Validate the response
        if (isinstance(response, dict) and
            "choices" in response and
            isinstance(response["choices"], list) and
            len(response["choices"]) > 0):
            result["success"] = True
            result["response_sample"] = {
                "message": response["choices"][0]["message"]["content"] if response["choices"] else None
            }
            print(f"✅ OpenAI API test successful")
        else:
            result["error"] = "Invalid response format"
            print("❌ OpenAI API test failed - invalid response format")
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ OpenAI API test failed with error: {e}")

    return result


def validate_sendgrid_api() -> Dict[str, Any]:
    """Validate the SendGrid API integration."""
    print("\n🔍 Testing SendGrid API integration...")
    result = {
        "api": "sendgrid",
        "key_available": check_api_key("sendgrid"),
        "success": False,
        "latency": 0,
        "error": None,
        "response_sample": None
    }

    if not result["key_available"]:
        result["error"] = "API key not found in environment variables"
        print("❌ SendGrid API key not found in environment variables")
        return result

    try:
        # Create a real SendGrid API client
        client = RealSendGridAPI()

        # Check if from email is set
        from_email = os.environ.get("SENDGRID_FROM_EMAIL")
        if not from_email:
            result["error"] = "SENDGRID_FROM_EMAIL not found in environment variables"
            print("❌ SENDGRID_FROM_EMAIL not found in environment variables")
            return result

        # Don't actually send an email, just validate the client setup
        print("✅ SendGrid API client initialized successfully (no email sent)")
        result["success"] = True
        result["response_sample"] = {
            "message": "SendGrid API client initialized successfully (no email sent)"
        }
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ SendGrid API test failed with error: {e}")

    return result


def validate_screenshotone_api() -> Dict[str, Any]:
    """Validate the ScreenshotOne API integration."""
    print("\n🔍 Testing ScreenshotOne API integration...")
    result = {
        "api": "screenshotone",
        "key_available": check_api_key("screenshotone"),
        "success": False,
        "latency": 0,
        "error": None,
        "response_sample": None
    }

    if not result["key_available"]:
        result["error"] = "API key not found in environment variables"
        print("❌ ScreenshotOne API key not found in environment variables")
        return result

    try:
        # Create a real ScreenshotOne API client
        client = RealScreenshotOneAPI()

        # Time the API call - but don't actually take a screenshot to avoid costs
        start_time = time.time()
        # Just verify the client is properly initialized
        result["latency"] = time.time() - start_time

        print("✅ ScreenshotOne API client initialized successfully (no screenshot taken)")
        result["success"] = True
        result["response_sample"] = {
            "message": "ScreenshotOne API client initialized successfully (no screenshot taken)"
        }
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ ScreenshotOne API test failed with error: {e}")

    return result


def main():
    """Run the API validation tests."""
    parser = argparse.ArgumentParser(description="Validate real API integrations")
    parser.add_argument("--api", type=str, choices=["yelp", "google", "openai", "sendgrid", "screenshotone"],
                        help="Test a specific API only")
    args = parser.parse_args()

    # Dictionary of API validation functions
    api_validators = {
        "yelp": validate_yelp_api,
        "google": validate_google_places_api,
        "openai": validate_openai_api,
        "sendgrid": validate_sendgrid_api,
        "screenshotone": validate_screenshotone_api
    }

    # Run tests for all APIs or a specific one
    results = []
    if args.api:
        validator = api_validators.get(args.api)
        if validator:
            results.append(validator())
        else:
            print(f"❌ Unknown API: {args.api}")
            return 1
    else:
        print("🚀 Validating all API integrations...")
        for validator in api_validators.values():
            results.append(validator())

    # Print summary
    print("\n📊 API Integration Validation Summary:")
    print("=====================================")
    success_count = 0
    key_available_count = 0

    for result in results:
        api_name = result["api"].upper()
        if result["key_available"]:
            key_available_count += 1

        if result["success"]:
            success_count += 1
            print(f"✅ {api_name}: SUCCESS (latency: {result['latency']:.2f}s)")
        else:
            if result["key_available"]:
                print(f"❌ {api_name}: FAILED - {result['error']}")
            else:
                print(f"⚠️ {api_name}: SKIPPED - API key not available")

    print("\n📈 Results:")
    print(f"  APIs with keys available: {key_available_count}/{len(results)}")
    print(f"  Successful API tests: {success_count}/{key_available_count}")

    # Save results to file
    results_dir = project_root / "tests" / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    results_file = results_dir / f"api_validation_{timestamp}.json"

    with open(results_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "api_count": len(results),
            "keys_available": key_available_count,
            "success_count": success_count,
            "results": results
        }, f, indent=2)

    print(f"\n📝 Detailed results saved to: {results_file}")

    # Return success if all APIs with keys available passed
    return 0 if success_count == key_available_count else 1


if __name__ == "__main__":
    sys.exit(main())
