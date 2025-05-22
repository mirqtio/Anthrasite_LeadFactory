# Contributing to Anthrasite LeadFactory

This document outlines the development workflow and best practices for contributing to the Anthrasite LeadFactory project.

## Development Workflow

Follow these steps for a smooth development experience:

1. **Clone the repository**
   ```bash
   git clone https://github.com/anthrasite/lead-factory.git
   cd lead-factory
   ```

2. **Set up your environment**
   ```bash
   # Create a virtual environment
   python -m venv .venv

   # Activate the virtual environment
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

4. **Write code**
   - Follow the project's code style and conventions
   - Write tests for your changes
   - Keep commits focused and atomic

5. **Run pre-commit hooks**
   ```bash
   pre-commit run --all-files
   ```

6. **Run tests**
   ```bash
   # Run fast tests during development
   pytest -m 'not slow'

   # Run all tests before pushing
   pytest
   ```

7. **Push changes and create a PR**
   ```bash
   git push origin your-branch-name
   ```

8. **Wait for CI to pass**
   - All checks must pass before merging
   - Address any issues raised by reviewers

## Code Style and Standards

- Follow PEP 8 style guidelines for Python code
- Use meaningful variable and function names
- Write docstrings for all public functions, classes, and modules
- Keep functions focused and not too long
- Use type hints where appropriate

## Testing Guidelines

- Write unit tests for all new functionality
- Maintain or improve code coverage
- Use pytest fixtures for test setup
- Mock external dependencies
- Use parameterized tests for testing multiple scenarios

## Pre-commit Hooks

The project uses the following pre-commit hooks:

- **ruff**: Lints Python code and sorts imports
- **black**: Formats Python code
- **bandit**: Checks for security issues
- **detect-secrets**: Prevents accidental secret leaks
- **pre-commit-hooks**: Various code quality checks

## CI Pipeline

The CI pipeline runs the following checks:

1. **Linting**: Ensures code follows style guidelines
2. **Unit Tests**: Runs all tests with pytest
3. **Security Checks**: Scans for security vulnerabilities
4. **Type Checking**: Verifies type annotations

## Dependency Management

- Add new dependencies to `requirements.txt` or `requirements-dev.txt` as appropriate
- Include version constraints for all dependencies
- Document why a dependency is needed in a comment

## Documentation

- Update documentation when changing functionality
- Document new features, APIs, and configuration options
- Keep the README up to date

## Releasing

- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Update the CHANGELOG.md file with all significant changes
- Tag releases with the version number

## Getting Help

If you have questions or need help, please:

1. Check the existing documentation
2. Look for similar issues in the issue tracker
3. Ask in the project's communication channels

Thank you for contributing to Anthrasite LeadFactory!
