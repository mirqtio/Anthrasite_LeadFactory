#!/usr/bin/env python3
"""
Check available OpenAI models with the API key in .env
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the API key
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
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

    for _model in completion_models:
        pass

    all_models = sorted([model["id"] for model in models["data"]])
    for _model in all_models:
        pass

except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        pass
    sys.exit(1)
except Exception:
    sys.exit(1)
