"""
Setup script for the leadfactory package.
"""

from pathlib import Path

from setuptools import find_packages, setup

# Read requirements.txt
requirements_path = Path(__file__).parent / "requirements" / "requirements.txt"
with open(requirements_path, "r") as f:
    # Filter out comments and empty lines, and normalize version constraints
    install_requires = []
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            install_requires.append(line)

# Read long description from README.md if it exists
long_description = ""
readme_path = Path(__file__).parent / "README.md"
if readme_path.exists():
    with open(readme_path, "r") as f:
        long_description = f.read()

setup(
    name="leadfactory",
    version="0.3.0",
    description="A pipeline for automatically scraping, enriching, scoring, and reaching out to SMB leads",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Anthrasite",
    author_email="info@anthrasite.io",
    url="https://github.com/mirqtio/Anthrasite_LeadFactory",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=install_requires,
    extras_require={
        "dev": [
            "pre-commit>=3.3.3",
            "ruff>=0.1.3",
            "black>=24.0.0",
            "flake8>=6.0.0",
            "isort>=5.12.0",
            "mypy>=1.5.1",
            "bandit>=1.7.5",
            "pytest>=7.4.0",
            "pytest-bdd>=6.1.1",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.1",
            "responses>=0.23.1",
            "sphinx>=7.1.2",
            "sphinx-rtd-theme>=1.3.0",
        ],
        "metrics": [
            "fastapi>=0.95.2",
            "uvicorn>=0.22.0",
            "prometheus-client>=0.17.1",
            "python-multipart>=0.0.6",
            "pydantic>=1.10.8",
        ],
    },
    entry_points={
        "console_scripts": [
            # Pipeline components
            "leadfactory-scrape=leadfactory.pipeline.scrape:main",
            "leadfactory-enrich=leadfactory.pipeline.enrich:main",
            "leadfactory-dedupe=leadfactory.pipeline.dedupe:main",
            "leadfactory-score=leadfactory.pipeline.score:main",
            "leadfactory-mockup=leadfactory.pipeline.mockup:main",
            "leadfactory-email=leadfactory.pipeline.email_queue:main",
            # Cost management
            "leadfactory-budget-gate=leadfactory.cost.budget_gate:main",
            "leadfactory-budget-audit=leadfactory.cost.budget_audit:main",
            "leadfactory-cost-tracking=leadfactory.cost.cost_tracking:main",
            # Utilities
            "leadfactory-metrics=leadfactory.utils.metrics:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Libraries",
    ],
)
