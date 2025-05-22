#!/usr/bin/env python3
"""
Comprehensive CI pipeline fix script.
This script addresses both formatting issues and test failures.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command, cwd=None, env=None):
    """Run a command and return its output."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Error: {e.stderr}"


def fix_formatting(project_root):
    """Fix formatting issues in the codebase."""
    print("🔧 Fixing formatting issues...")
    
    # Fix import sorting with ruff
    success, output = run_command(
        ["ruff", "check", "--select=I", "--fix", "."],
        cwd=project_root
    )
    if not success:
        print(f"❌ Failed to fix imports: {output}")
    else:
        print("✅ Fixed imports with ruff")
    
    # Format code with black
    success, output = run_command(
        ["black", ".", "--config", ".black.toml"],
        cwd=project_root
    )
    if not success:
        print(f"❌ Failed to format code: {output}")
    else:
        print("✅ Formatted code with black")


def fix_test_imports(project_root):
    """Fix import issues in test files."""
    print("🔧 Fixing test import issues...")
    
    test_dir = os.path.join(project_root, "tests")
    if not os.path.exists(test_dir):
        print("❌ Tests directory not found")
        return
    
    # Add __init__.py to tests directory if it doesn't exist
    init_file = os.path.join(test_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("# This file is required for pytest to discover tests correctly\n")
        print(f"✅ Created {init_file}")
    
    # Fix conftest.py if it exists
    conftest_file = os.path.join(test_dir, "conftest.py")
    if os.path.exists(conftest_file):
        with open(conftest_file, "r") as f:
            content = f.read()
        
        # Add sys.path.insert if not present
        if "sys.path.insert" not in content:
            with open(conftest_file, "w") as f:
                f.write("import os\nimport sys\n\n")
                f.write("# Add project root to path\n")
                f.write("sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n\n")
                f.write(content)
            print(f"✅ Fixed {conftest_file}")


def create_env_file(project_root):
    """Create or update .env file with test values."""
    print("🔧 Creating/updating .env file for tests...")
    
    env_file = os.path.join(project_root, ".env")
    env_example = os.path.join(project_root, ".env.example")
    
    if os.path.exists(env_example) and not os.path.exists(env_file):
        # Copy .env.example to .env
        with open(env_example, "r") as src:
            content = src.read()
        
        # Replace API keys with mock values
        content = content.replace("your_yelp_api_key_here", "mock_yelp_key")
        content = content.replace("your_google_places_api_key_here", "mock_google_key")
        content = content.replace("your_openai_api_key_here", "mock_openai_key")
        content = content.replace("your_anthropic_api_key_here", "mock_anthropic_key")
        content = content.replace("your_sendgrid_api_key_here", "mock_sendgrid_key")
        
        # Set database URL for testing
        content = content.replace(
            "postgresql://postgres:postgres@localhost:5432/leadfactory",
            "postgresql://postgres:postgres@localhost:5432/leadfactory_test"
        )
        
        with open(env_file, "w") as dest:
            dest.write(content)
        
        print(f"✅ Created {env_file} with mock values")


def create_missing_directories(project_root):
    """Create any missing directories required for tests."""
    print("🔧 Creating missing directories...")
    
    # Ensure data directory exists
    data_dir = os.path.join(project_root, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"✅ Created {data_dir}")
    
    # Ensure html_storage directory exists
    html_storage = os.path.join(data_dir, "html_storage")
    if not os.path.exists(html_storage):
        os.makedirs(html_storage)
        print(f"✅ Created {html_storage}")
    
    # Ensure tasks directory exists
    tasks_dir = os.path.join(project_root, "tasks")
    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)
        print(f"✅ Created {tasks_dir}")


def main():
    """Main function to fix CI pipeline issues."""
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Fix formatting issues
    fix_formatting(project_root)
    
    # Fix test import issues
    fix_test_imports(project_root)
    
    # Create/update .env file
    create_env_file(project_root)
    
    # Create missing directories
    create_missing_directories(project_root)
    
    print("\n✅ CI pipeline fixes completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
