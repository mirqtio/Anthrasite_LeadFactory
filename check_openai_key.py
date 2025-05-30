#!/usr/bin/env python3
"""Quick script to test the OpenAI API key from the .env file directly"""

import os
import sys
from pathlib import Path

import requests


def read_key_from_env_file(file_path=".env"):
    """Read the OpenAI API key directly from the .env file"""
    try:
        with open(file_path, "r") as f:
            for line in f:
                if line.strip().startswith("OPENAI_API_KEY="):
                    # Extract everything after the equals sign
                    return line.strip().split("=", 1)[1].strip("\"'")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def test_openai_key(api_key):
    """Test the OpenAI API key by making a simple API call"""
    print(f"Testing key: {api_key[:10]}...{api_key[-4:]}")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello world"},
        ],
        "max_tokens": 10,
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]["content"]
            print(f"✅ API call successful! Response: {message}")
            return True
        else:
            print(f"❌ API call failed with status code {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return False


if __name__ == "__main__":
    # Read the key directly from the .env file
    api_key = read_key_from_env_file()

    if not api_key:
        print("❌ Could not find OPENAI_API_KEY in .env file")
        sys.exit(1)

    # Test the key
    success = test_openai_key(api_key)

    if success:
        print("\n🎉 Your OpenAI API key from the .env file is working correctly!")
    else:
        print("\n❌ Your OpenAI API key from the .env file is not working.")
        print("Please check that it's valid and has sufficient credits.")

    # For diagnostic purposes, show what's in the environment variable
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        print(f"\nℹ️ Note: Your system environment also has an OPENAI_API_KEY set.")
        print(
            f"System env key: {env_key[:5]}...{env_key[-4:] if len(env_key) > 8 else env_key}"
        )
        if env_key != api_key:
            print("⚠️ Warning: This is different from the key in your .env file!")
            print("This may explain any inconsistent behavior you're experiencing.")
            print(
                "Applications using dotenv will prioritize environment variables over .env file values."
            )
    else:
        print("\nℹ️ Note: No OPENAI_API_KEY found in system environment variables.")
