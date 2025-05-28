# E2E Preflight Check System

A comprehensive validation system that checks all required components (environment variables, API connections, database access, and pipeline services) are properly configured and operational before running E2E tests.

## Overview

The E2E Preflight Check system is designed to validate the test environment before running end-to-end tests. It ensures that all required components are properly configured and operational, preventing test failures due to environment issues rather than code issues.

The system consists of four main components:

1. **Configuration Validator** - Validates required environment variables and their formats
2. **API Connectivity Tester** - Verifies connectivity to external APIs (OpenAI, Google Maps, SendGrid)
3. **Database Connectivity Verifier** - Validates database connection, schema, and sample data
4. **Pipeline Component Validator** - Checks that all pipeline services are operational

## Installation

No additional installation is required beyond the standard project dependencies. The preflight check system is built into the project.

## Usage

### Basic Usage

Run the preflight check system with default settings:

```bash
python scripts/preflight/preflight_check.py
```

This will:
1. Validate environment variables
2. Test API connectivity
3. Verify database connection and schema
4. Check pipeline components

The system will exit with code 0 if all checks pass, or a non-zero code if any check fails.

### Command-line Options

```bash
python scripts/preflight/preflight_check.py --env /path/to/.env.e2e --log /path/to/log/file.log --report /path/to/report.txt
```

Available options:
- `--env`: Path to the environment file (default: .env.e2e)
- `--log`: Path to log file for preflight check results
- `--report`: Path to output report file
- `--generate-sample-env`: Generate sample environment files for all components

### Mock Mode

For testing without making actual API calls or database connections, set `MOCKUP_ENABLED=true` in your environment file.

## Components

### Configuration Validator

The Configuration Validator checks that all required environment variables are present and have valid formats. It validates:

- Core configuration variables (E2E_MODE, MOCKUP_ENABLED)
- Database connection parameters
- API keys (OpenAI, Google Maps, SendGrid)
- Email settings
- Pipeline configuration

Usage:
```python
from scripts.preflight.config_validator import ConfigValidator

validator = ConfigValidator(env_file='.env.e2e')
result = validator.validate()

if result.success:
    print("Configuration is valid")
else:
    print("Configuration issues:")
    for issue in result.issues:
        print(f"- {issue}")
```

### API Connectivity Tester

The API Connectivity Tester verifies connectivity to all required external APIs. It checks:

- OpenAI API connectivity
- Google Maps API connectivity
- SendGrid API connectivity

Each API test performs a lightweight request to verify connectivity and proper authentication.

Usage:
```python
from scripts.preflight.api_tester import ApiTester

tester = ApiTester(env_file='.env.e2e')
results = tester.test_all_apis()

for api_name, result in results.items():
    if result.success:
        print(f"{api_name}: ✅ {result.message}")
    else:
        print(f"{api_name}: ❌ {result.message}")
```

### Database Connectivity Verifier

The Database Connectivity Verifier checks connectivity to the PostgreSQL database and validates the schema and sample data. It verifies:

- Database connection
- Required tables and schema
- Sample data presence
- Docker container status

Usage:
```python
from scripts.preflight.db_verifier import DbVerifier

verifier = DbVerifier(env_file='.env.e2e')
result = verifier.verify_database()

if result.success:
    print("Database verification successful")
else:
    print("Database verification failed:")
    for issue in result.issues:
        print(f"- {issue}")
```

### Pipeline Component Validator

The Pipeline Component Validator checks that all pipeline services and components are properly configured and operational. It verifies:

- Pipeline component connectivity
- Pipeline service status
- Docker services status
- Pipeline component connections

Usage:
```python
from scripts.preflight.pipeline_validator import PipelineValidator

validator = PipelineValidator(env_file='.env.e2e')
result = validator.validate()

if result.success:
    print("Pipeline validation successful")
else:
    print("Pipeline validation failed:")
    for issue in result.issues:
        print(f"- {issue}")
```

## Sample Environment Files

Generate sample environment files for all components:

```bash
python scripts/preflight/preflight_check.py --generate-sample-env
```

This will generate:
- sample_config.env: Configuration variables
- sample_api.env: API connectivity variables
- sample_db.env: Database connectivity variables
- sample_pipeline.env: Pipeline component variables
- sample_e2e.env: Combined environment file

## Troubleshooting

### Common Issues and Solutions

#### Environment Variable Issues

**Problem**: Missing required environment variables
- **Error**: `Missing required variable: [VARIABLE_NAME]`
- **Solution**: Add the missing variable to your `.env.e2e` file. Generate a sample file with `--generate-sample-env` option.

**Problem**: Invalid API key format
- **Error**: `Invalid format for [API_NAME] API key`
- **Solution**: Check that the API key matches the expected format and is valid.

#### API Connectivity Issues

**Problem**: API authentication failure
- **Error**: `[API_NAME] returned status code 401`
- **Solution**: Verify your API key is valid and has not expired.

**Problem**: API connection timeout
- **Error**: `[API_NAME] connection error: Connection timed out`
- **Solution**: Check your internet connection and firewall settings.

#### Database Issues

**Problem**: Database connection failure
- **Error**: `Database connection failed: Connection refused`
- **Solution**: Verify the database is running and the connection string is correct.

**Problem**: Missing required tables
- **Error**: `Table [TABLE_NAME] does not exist`
- **Solution**: Run database migrations or use a properly seeded database.

**Problem**: Docker container not running
- **Error**: `Database container does not exist` or `Database container is not running`
- **Solution**: Start the database Docker container.

#### Pipeline Component Issues

**Problem**: Pipeline component not responding
- **Error**: `Failed to connect to [COMPONENT]: Connection refused`
- **Solution**: Ensure the component service is running.

**Problem**: Pipeline component authentication failure
- **Error**: `[COMPONENT] returned status code 401`
- **Solution**: Check the component's authentication configuration.

## Extending the System

To add new preflight checks:

1. Identify the appropriate component for your check
2. Add the check to the relevant component
3. Update the component's validation method to include your check
4. Update the issues list and success flag if the check fails

Example:
```python
def check_new_requirement(self) -> Tuple[bool, List[str]]:
    """Check a new requirement."""
    issues = []
    # Your check logic here
    if problem_detected:
        issues.append("Description of the problem")
    return len(issues) == 0, issues
```

## Contributing

Contributions to the E2E Preflight Check system are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Add tests for your changes
5. Run the tests to ensure they pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
