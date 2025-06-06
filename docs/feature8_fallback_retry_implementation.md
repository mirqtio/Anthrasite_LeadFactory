# Feature 8: Fallback & Retry Implementation

This document describes the implementation of Feature 8: Fallback & Retry, which includes FL-3 manual fix scripts and FL-4 bulk dismiss UI for comprehensive error management.

## Overview

Feature 8 provides automated error resolution capabilities and bulk error management operations to improve pipeline reliability and reduce manual intervention requirements.

## Components Implemented

### FL-3: Manual Fix Scripts

**Location**: `leadfactory/pipeline/manual_fix_scripts.py`

Automated fix scripts for common pipeline errors:

1. **DatabaseConnectionFix**: Resolves database connection timeouts and pool exhaustion
2. **NetworkTimeoutFix**: Handles network timeouts and API connection issues
3. **ValidationErrorFix**: Cleans and standardizes invalid business data
4. **ResourceExhaustionFix**: Frees up disk space and memory resources
5. **ExternalAPIErrorFix**: Rotates API keys and manages rate limiting

#### Key Features:
- Automatic error classification and fix script selection
- Execution logging and result tracking
- Configurable retry strategies and circuit breakers
- Fix orchestrator for coordinating multiple scripts

#### Usage Example:
```python
from leadfactory.pipeline.manual_fix_scripts import manual_fix_orchestrator

# Apply fixes to an error
executions = manual_fix_orchestrator.fix_error(pipeline_error)

# Check fix results
for execution in executions:
    if execution.result == FixResult.SUCCESS:
        print(f"Error fixed by {execution.fix_id}")
```

### FL-4: Bulk Dismiss UI

**Location**: `leadfactory/api/error_management_api.py` and `leadfactory/static/error_management.html`

Web-based interface for bulk error management operations:

#### API Endpoints:
- `POST /api/errors/bulk-dismiss`: Dismiss multiple errors with reason
- `POST /api/errors/bulk-categorize`: Update category/severity/tags in bulk
- `POST /api/errors/bulk-fix`: Apply fix scripts to multiple errors
- `GET /api/errors/dashboard-data`: Comprehensive error dashboard data

#### UI Features:
- Real-time error list with filtering
- Bulk selection and operations
- Progress indicators and feedback
- Error pattern visualization
- Fix script effectiveness metrics

#### Usage:
1. Navigate to `/error_management.html`
2. Filter and select errors for bulk operations
3. Choose operation: dismiss, categorize, or fix
4. Monitor progress and view results

### Error Monitoring and Reporting

**Location**: `leadfactory/monitoring/fix_script_monitoring.py`

Comprehensive monitoring system for fix script effectiveness:

#### Features:
- Performance metrics and success rate tracking
- Alert generation for degraded performance
- Trend analysis and recommendations
- Historical reporting and analytics

#### Metrics Tracked:
- Fix script execution success rates
- Average execution duration
- Error pattern frequency
- Business impact analysis

#### Alert Conditions:
- Success rate below 70% (warning) or 50% (critical)
- Failure rate above 30% (warning) or 50% (critical)
- Average duration above 30s (warning) or 60s (critical)

### Retry Mechanisms and Circuit Breakers

**Location**: `leadfactory/pipeline/retry_mechanisms.py` (enhanced)

Enhanced retry system with circuit breaker pattern:

#### Features:
- Configurable retry strategies (exponential, linear, immediate)
- Circuit breaker to prevent cascading failures
- Jitter to prevent thundering herd
- Statistics and monitoring integration

#### Circuit Breaker States:
- **CLOSED**: Normal operation
- **OPEN**: Rejecting calls due to failures
- **HALF_OPEN**: Testing recovery

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Error Occurs  │───▶│   Fix Scripts    │───▶│   Monitoring    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Bulk UI       │◀───│   Orchestrator   │───▶│   Alerting      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                       │                         │
        ▼                       ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Layer     │    │   Storage Layer  │    │   Reporting     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Configuration

### Fix Script Configuration

Configure fix scripts through environment variables or storage:

```python
# Example configuration for database fix
{
    "max_retries": 3,
    "timeout_multiplier": 2.0,
    "connection_pool_size": 10
}
```

### Circuit Breaker Configuration

```python
circuit_breaker_config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=60.0,    # Wait 60s before trying again
    success_threshold=3       # Close after 3 successes
)
```

### Alert Thresholds

```python
alert_thresholds = {
    'success_rate_warning': 70.0,    # Warn if < 70% success rate
    'success_rate_critical': 50.0,   # Critical if < 50% success rate
    'avg_duration_warning': 30.0,    # Warn if > 30s average duration
}
```

## Testing

### BDD Tests

**Location**: `tests/bdd/features/fallback_retry.feature`

Comprehensive BDD scenarios covering:
- Manual fix script operations
- Bulk error management workflows
- Error pattern detection
- Circuit breaker behavior
- Monitoring and alerting

### Integration Tests

**Location**: `tests/integration/test_error_management_integration.py`

End-to-end integration tests for:
- Complete error resolution workflow
- Bulk operations with API
- Fix script monitoring
- Dashboard data generation

### Running Tests

```bash
# Run BDD tests
pytest tests/bdd/features/fallback_retry.feature -v

# Run integration tests
pytest tests/integration/test_error_management_integration.py -v

# Run all error management tests
pytest -k "error_management" -v
```

## Deployment

### Dependencies

Add to `requirements.txt`:
```
# Already included in existing requirements
```

### Database Schema

No additional database schema changes required. The system uses existing error storage mechanisms.

### API Integration

Register the error management API blueprint:

```python
from leadfactory.api.error_management_api import error_management
app.register_blueprint(error_management)
```

### UI Deployment

Deploy the error management UI by ensuring the static files are served:

```python
# In your Flask app configuration
app.static_folder = 'leadfactory/static'
```

## Monitoring and Operations

### Dashboard Access

Access the error management dashboard at:
- UI: `/error_management.html`
- API: `/api/errors/dashboard-data`

### Key Metrics to Monitor

1. **Fix Script Performance**:
   - Overall success rate: Should be > 80%
   - Average execution time: Should be < 15 seconds
   - Pattern detection effectiveness

2. **Error Patterns**:
   - Recurring error frequency
   - New error types introduction
   - Resolution time trends

3. **System Health**:
   - Circuit breaker state changes
   - Alert frequency and severity
   - Manual intervention requirements

### Troubleshooting

#### Common Issues

1. **Fix Scripts Not Working**:
   - Check storage connectivity
   - Verify fix script error pattern matching
   - Review execution logs for errors

2. **High Alert Volume**:
   - Adjust alert thresholds
   - Review error categorization
   - Check for new error patterns

3. **UI Not Loading**:
   - Verify API endpoints are accessible
   - Check CORS configuration
   - Review browser console for errors

#### Log Analysis

Fix script execution logs include:
- Fix script ID and execution timestamp
- Error details and context
- Changes made and results
- Duration and performance metrics

## Future Enhancements

### Planned Improvements

1. **Machine Learning Integration**:
   - Predictive error pattern detection
   - Automated fix script generation
   - Success rate optimization

2. **Advanced Retry Strategies**:
   - Adaptive retry intervals
   - Context-aware retry logic
   - Cross-service coordination

3. **Enhanced UI Features**:
   - Real-time error stream
   - Interactive trend analysis
   - Custom alert configuration

### Extension Points

The system is designed for extensibility:

1. **Custom Fix Scripts**: Inherit from `ManualFixScript` base class
2. **Custom Monitoring**: Implement additional `FixScriptMonitor` methods
3. **Custom UI Components**: Extend the HTML/JavaScript interface
4. **Integration Hooks**: Add event handlers for fix script execution

## Security Considerations

### Access Control

- API endpoints require appropriate authentication
- Bulk operations are rate-limited
- User actions are logged for audit trails

### Data Privacy

- Error messages may contain sensitive information
- Implement data sanitization for logs
- Respect data retention policies

### Operational Security

- Fix scripts have limited scope and permissions
- Circuit breakers prevent resource exhaustion
- Monitoring includes security event detection

## Performance Impact

### Resource Usage

- Fix scripts: Minimal CPU impact, brief execution times
- Monitoring: Low overhead, configurable collection intervals
- UI: Client-side processing, efficient API queries

### Scalability

- Fix scripts can be executed in parallel
- Monitoring data can be aggregated across instances
- UI supports pagination for large error volumes

### Optimization Tips

1. Tune alert thresholds based on system characteristics
2. Implement fix script caching for common patterns
3. Use database indexing for error query performance
4. Consider async processing for large bulk operations

---

For questions or support regarding Feature 8 implementation, please refer to the test files and API documentation, or contact the development team.
