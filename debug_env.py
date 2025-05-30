#!/usr/bin/env python3
"""Debug script to check environment variables"""

import os
import sys
from pathlib import Path

# Try different methods of loading .env file
with open(".env") as f:
    for line in f:
        if "OPENAI_API_KEY" in line:
            pass

if "OPENAI_API_KEY" in os.environ:
    pass
else:
    pass

# Try to load with python-dotenv
try:
    from dotenv import load_dotenv

    # First, see what files exist
    env_files = [".env", ".env.production", ".env.real_test"]
    for env_file in env_files:
        if Path(env_file).exists():
            pass
        else:
            pass

    # Try loading .env with dotenv
    load_dotenv(".env")
    if "OPENAI_API_KEY" in os.environ:
        pass
    else:
        pass

except ImportError:
    pass

# Check if file is binary or has unexpected encoding
try:
    with open(".env", "rb") as f:
        content = f.read()
        has_binary = any(c > 127 for c in content)
        if has_binary:
            pass
        else:
            pass
except Exception:
    pass

os.system("ls -la .env*")

os.system("file .env")
