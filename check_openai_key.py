#!/usr/bin/env python3
"""Quick script to test the OpenAI API key from the .env file directly"""

import os
import sys
from pathlib import Path

import requests


def read_key_from_env_file(file_path=".env"):
    """Read the OpenAI API key directly from the .env file"""
    try:
        with open(file_path) as f:
            for line in f:
                if line.strip().startswith("OPENAI_API_KEY="):
                    # Extract everything after the equals sign
                    return line.strip().split("=", 1)[1].strip("\"'")
    except Exception:
        return None


def test_openai_key(api_key):
    """Test the OpenAI API key by making a simple API call"""

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
            result["choices"][0]["message"]["content"]
            return True
        else:
            return False
    except Exception:
        return False


if __name__ == "__main__":
    # Read the key directly from the .env file
    api_key = read_key_from_env_file()

    if not api_key:
        sys.exit(1)

    # Test the key
    success = test_openai_key(api_key)

    if success:
        pass
    else:
        pass

    # For diagnostic purposes, show what's in the environment variable
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        if env_key != api_key:
            pass
    else:
        pass
