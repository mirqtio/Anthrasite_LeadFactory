# LeadFactory Test Suite

This directory contains tests for the LeadFactory application. The test suite is structured to provide comprehensive coverage of all modules and features in the application.

## Test Structure

The test suite is organized into the following directories:

- `unit/`: Unit tests for individual components and functions
- `integration/`: Tests that verify the interaction between multiple components
- `bdd/`: Behavior-driven development tests that verify user-facing features
- `utils/`: Shared test utilities and fixtures

## Running Tests

To run the entire test suite:

```bash
python -m pytest
```

To run specific test categories:

```bash
# Run unit tests only
python -m pytest tests/unit/

# Run integration tests only
python -m pytest tests/integration/

# Run BDD tests only
python -m pytest tests/bdd/

# Run with verbose output
python -m pytest -v

# Run with coverage report
python -m pytest --cov=bin
```

## Test Fixtures

The test suite uses fixtures to provide common setup and teardown functionality across tests. The main fixtures are defined in `conftest.py` and include:

- Database fixtures for creating and managing test databases
- API mock fixtures for mocking external API calls
- Test data fixtures for generating consistent test data
- Pipeline stage fixtures for testing pipeline stages

Additional specialized fixtures are defined in individual test modules.

## Parameterized Tests

The test suite makes extensive use of parameterized tests to improve coverage with minimal code duplication. This approach allows testing multiple scenarios with a single test function.

Examples:

- `test_parameterized.py`: Demonstrates parameterization techniques
- `test_email_parameterized.py`: Parameterized tests for email functionality
- `test_budget_parameterized.py`: Parameterized tests for budget functionality
- `test_dedupe_parameterized.py`: Parameterized tests for deduplication functionality
- `test_scrape_parameterized.py`: Parameterized tests for scraping functionality

## Test Data Generation

The `tests/utils/test_utils.py` module provides functions for generating test data:

- Business data generation with various characteristics
- Duplicate pair generation
- Email generation
- API cost record generation

## Mock Objects

Mock objects are provided for external dependencies:

- `MockLevenshteinMatcher`: For testing deduplication matching
- `MockOllamaVerifier`: For testing LLM-based verification
- `MockRequests`: For testing HTTP requests
- `MockResponse`: For testing HTTP responses

## Integration Testing

Integration tests verify that the different modules of the application work together correctly:

- `test_dedupe_process.py`: Tests the deduplication workflow
- `test_email_queue_process.py`: Tests the email generation and sending workflow
- `test_full_pipeline.py`: Tests the entire pipeline from scraping to email generation

## BDD Testing

BDD tests use the pytest-bdd plugin to implement feature files and step definitions:

- `tests/bdd/features/`: Contains feature files written in Gherkin syntax
- `tests/bdd/step_defs/`: Contains step definitions that implement the feature scenarios
