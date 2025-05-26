#!/usr/bin/env python3
"""
Check available OpenAI models with the API key in .env
"""

import os
import json
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the API key
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("OpenAI API key not found in environment variables")
    sys.exit(1)

# Set up headers
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Make request to list models
try:
    response = requests.get("https://api.openai.com/v1/models", headers=headers)
    response.raise_for_status()
    models = response.json()

    # Filter for completion models
    completion_models = [
        model for model in models["data"]
        if "gpt" in model["id"].lower() or
           any(id_part in model["id"].lower() for id_part in ["turbo", "text-davinci"])
    ]

    # Sort models by id
    completion_models.sort(key=lambda x: x["id"])

    print(f"Found {len(completion_models)} completion models:")
    for model in completion_models:
        print(f"- {model['id']}")

    print("\nFull list of all models:")
    all_models = sorted([model["id"] for model in models["data"]])
    for model in all_models:
        print(f"- {model}")

except requests.exceptions.HTTPError as e:
    print(f"Error: {e}")
    if e.response.status_code == 401:
        print("Authentication error: Please check your API key")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
