# Failover Threshold Adjustment

## Overview

This document describes the implementation of the failover threshold adjustment for the Anthrasite LeadFactory. The adjustment changes the `HEALTH_CHECK_FAILURES_THRESHOLD` from 3 to 2 consecutive failures to match the Phase 0 "Lead-Factory" spec v1.3 requirements.

## Changes Made

1. Updated the `FAILURE_THRESHOLD` constant in `bin/health_check.sh` from 3 to 2
2. Updated the sample configuration file `etc/health_check_config.yml.sample` to reflect the new threshold value
3. Updated the README.md to explicitly mention the new threshold value
4. Created a test script to verify the failover mechanism works correctly with the new threshold value

## Implementation Details

### Script Changes

The `FAILURE_THRESHOLD` constant in `bin/health_check.sh` was changed from 3 to 2:

```bash
# Before
FAILURE_THRESHOLD=3

# After
FAILURE_THRESHOLD=2  # Changed from 3 to 2 to match Phase 0 v1.3 spec
```

### Configuration Changes

The sample configuration file `etc/health_check_config.yml.sample` was updated to reflect the new threshold value:

```yaml
# Before
# Failure threshold
failure_threshold: 3

# After
# Failure threshold - set to 2 consecutive failures per Phase 0 v1.3 spec
failure_threshold: 2
```

### Documentation Changes

The README.md was updated to explicitly mention the new threshold value:

```markdown
# Before
2. Tracks failure count with configurable threshold

# After
2. Tracks failure count with configurable threshold (set to 2 consecutive failures per Phase 0 v1.3 spec)
```

### Testing

A test script `tests/test_health_check_threshold.sh` was created to verify that the failover mechanism works correctly with the new threshold value. The script tests the following scenarios:

1. 0 failures + success = 0 failures
2. 0 failures + failure = 1 failure
3. 1 failure + failure = 2 failures (should trigger boot)
4. 1 failure + success = 0 failures

## Impact

This change improves system reliability by triggering failover after fewer consecutive failures. The system will now boot the backup instance after 2 consecutive failures instead of 3, reducing the potential downtime in case of failures.

## Compliance

This change aligns the system with the Phase 0 "Lead-Factory" spec v1.3 requirements, which specify that the failover threshold should be set to 2 consecutive failures.

## Testing

The failover mechanism was tested with the new threshold value using the `tests/test_health_check_threshold.sh` script. The tests verified that:

1. The system correctly tracks consecutive failures
2. The system triggers failover after exactly 2 consecutive failures
3. The system resets the failure count after a successful health check

## Deployment

To deploy this change, existing installations should update their `health_check_config.yml` file to set the `failure_threshold` to 2. New installations will automatically use the new threshold value from the sample configuration file.

## Rollback

If needed, the threshold can be rolled back to 3 by reverting the changes to `bin/health_check.sh` and updating the configuration file.
