#!/usr/bin/env python3
"""
Creates the initial repository skeleton structure for the Anthrasite Lead-Factory project.
"""

from pathlib import Path

# Define the directory structure
DIRS = ["bin", "utils", "etc", "tests", "db/migrations", "db/seeds", "tmp"]

# Define stub files to create
STUBS = {
    "bin/__init__.py": "",
    "utils/__init__.py": "",
    "tests/__init__.py": "",
    "tests/conftest.py": """\"\"\"
Pytest configuration and fixtures for the Anthrasite Lead-Factory.
\"\"\"
import pytest
from pathlib import Path

# Add any project-wide test fixtures here
""",
    "requirements.txt": """# Core dependencies
pytest>=7.0.0
pytest-bdd>=6.0.0
requests>=2.28.0
python-dotenv>=0.20.0
sqlalchemy>=1.4.0
prometheus-client>=0.14.0
psycopg2-binary>=2.9.0
pytest-mock>=3.10.0
""",
    ".env.example": """# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/leadfactory

# API Keys (replace with actual values in .env)
YELP_API_KEY=your_yelp_api_key
GOOGLE_PLACES_API_KEY=your_google_places_api_key
SENDGRID_API_KEY=your_sendgrid_api_key

# Application Settings
LOG_LEVEL=INFO
ENVIRONMENT=development

# Budget Settings
DAILY_BUDGET_LIMIT=100.0
MONTHLY_BUDGET_LIMIT=2000.0
""",
}


def create_skeleton():
    """Create the directory structure and stub files."""
    # Create directories
    for directory in DIRS:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

    # Create stub files
    for file_path, content in STUBS.items():
        if not Path(file_path).exists():
            with open(file_path, "w") as f:
                f.write(content)
            print(f"Created file: {file_path}")

    # Make scripts executable
    for script in Path("bin").glob("*.py"):
        script.chmod(0o755)
        print(f"Made executable: {script}")


if __name__ == "__main__":
    create_skeleton()
    print("\nRepository skeleton created successfully!")
