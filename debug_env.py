#!/usr/bin/env python3
"""Debug script to check environment variables"""

import os
import sys
from pathlib import Path

# Try different methods of loading .env file
print("Method 1: Direct file reading")
with open(".env") as f:
    for line in f:
        if "OPENAI_API_KEY" in line:
            print(f"  Found in .env: {line.strip()}")

print("\nMethod 2: Using os.environ")
if "OPENAI_API_KEY" in os.environ:
    print(f"  Found in os.environ: OPENAI_API_KEY={os.environ['OPENAI_API_KEY']}")
else:
    print("  OPENAI_API_KEY not found in os.environ")

# Try to load with python-dotenv
try:
    print("\nMethod 3: Using python-dotenv")
    from dotenv import load_dotenv

    # First, see what files exist
    env_files = [".env", ".env.production", ".env.real_test"]
    for env_file in env_files:
        if Path(env_file).exists():
            print(f"  {env_file} exists")
        else:
            print(f"  {env_file} does not exist")

    # Try loading .env with dotenv
    print("\n  Loading .env with dotenv:")
    load_dotenv(".env")
    if "OPENAI_API_KEY" in os.environ:
        print(f"  After load_dotenv: OPENAI_API_KEY={os.environ['OPENAI_API_KEY']}")
    else:
        print("  OPENAI_API_KEY not found after load_dotenv")

except ImportError:
    print("  python-dotenv not installed")

# Check if file is binary or has unexpected encoding
print("\nMethod 4: Check for binary content or encoding issues")
try:
    with open(".env", "rb") as f:
        content = f.read()
        has_binary = any(c > 127 for c in content)
        if has_binary:
            print("  .env file contains binary (non-ASCII) data")
            print(f"  First 100 bytes: {content[:100]}")
        else:
            print("  .env file contains only ASCII data")
except Exception as e:
    print(f"  Error reading file: {e}")

print("\nMethod 5: List all files in directory with ls -la")
os.system("ls -la .env*")

print("\nMethod 6: Check if there's a symbolic link")
os.system("file .env")
