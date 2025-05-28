#!/bin/bash

# Add Phase 0 alignment review tasks

echo "Adding Phase 0 alignment review tasks..."

# Task 1: Implement Scoring Rule Evaluation Engine
task-master add-task \
  --title="Implement Scoring Rule Evaluation Engine" \
  --description="Full implementation of YAML-driven scoring, including tests and CI verification" \
  --priority=high \
  --dependencies="" \
  --details="Implement a comprehensive scoring rule evaluation engine that:
- Reads scoring rules from YAML configuration files
- Evaluates businesses against defined scoring criteria
- Supports multiple scoring dimensions (quality, engagement, conversion potential)
- Provides weighted scoring calculations
- Includes comprehensive unit tests
- Ensures CI pipeline verification passes" \
  --test-strategy="1. Unit tests for rule parsing and evaluation logic
2. Integration tests with sample business data
3. Performance tests for large datasets
4. CI pipeline must pass all tests"

# Task 2: Automate IP/Subuser Rotation for Bounce Thresholds (deferred)
task-master add-task \
  --title="Automate IP/Subuser Rotation for Bounce Thresholds" \
  --description="Automate IP rotation based on bounce rates, with tests" \
  --priority=medium \
  --status=deferred \
  --dependencies="" \
  --details="Implement automatic IP and subuser rotation when bounce thresholds are exceeded:
- Monitor bounce rates per IP/subuser
- Define configurable bounce rate thresholds
- Automatically rotate to next available IP/subuser when threshold exceeded
- Implement cooldown periods for rotated IPs
- Add comprehensive logging and alerting
- Include unit and integration tests" \
  --test-strategy="1. Unit tests for threshold monitoring logic
2. Integration tests with SendGrid API
3. Simulate bounce scenarios and verify rotation
4. Test alerting mechanisms"

# Task 3: Finalize Dedupe Integration with Unified Postgres Connector
task-master add-task \
  --title="Finalize Dedupe Integration with Unified Postgres Connector" \
  --description="Remove legacy references and ensure proper duplicate handling" \
  --priority=high \
  --dependencies="" \
  --details="Complete the deduplication integration:
- Remove all legacy dedupe code references
- Ensure unified Postgres connector handles all deduplication
- Implement proper conflict resolution for duplicate businesses
- Preserve data from multiple sources during deduplication
- Add comprehensive logging for dedupe operations
- Include performance optimizations for large datasets" \
  --test-strategy="1. Unit tests for dedupe logic
2. Integration tests with real duplicate scenarios
3. Performance tests with large datasets
4. Verify data preservation during merges"

# Task 4: Replace Legacy bin/ Scripts with CLI Wrappers
task-master add-task \
  --title="Replace Legacy bin/ Scripts with CLI Wrappers" \
  --description="Consolidate execution logic and remove old scripts" \
  --priority=medium \
  --dependencies="" \
  --details="Modernize script execution:
- Create CLI wrappers for all bin/ scripts
- Consolidate common functionality into shared modules
- Remove deprecated bin/ scripts
- Update documentation to reference new CLI commands
- Ensure backward compatibility where needed
- Add proper argument parsing and validation" \
  --test-strategy="1. Unit tests for CLI commands
2. Integration tests for each wrapper
3. Verify all functionality is preserved
4. Test backward compatibility"

# Task 5: Refactor PipelineValidator to Check Actual Stages
task-master add-task \
  --title="Refactor PipelineValidator to Check Actual Stages" \
  --description="Update validation logic and add tests" \
  --priority=high \
  --dependencies="" \
  --details="Refactor the pipeline validator to validate actual pipeline stages:
- Check each pipeline stage's requirements before execution
- Validate API keys, database connections, file permissions
- Ensure all dependencies are met for each stage
- Add stage-specific validation rules
- Implement proper error reporting
- Add comprehensive test coverage" \
  --test-strategy="1. Unit tests for each validation check
2. Integration tests with full pipeline
3. Test failure scenarios and error handling
4. Verify all stages are properly validated"

# Task 6: Enable Disabled Tests and Resolve Failures
task-master add-task \
  --title="Enable Disabled Tests and Resolve Failures" \
  --description="Identify and fix disabled tests, ensuring CI passes" \
  --priority=high \
  --dependencies="" \
  --details="Re-enable and fix all disabled tests:
- Audit all test files for disabled/skipped tests
- Identify root causes of test failures
- Fix underlying issues causing test failures
- Re-enable all tests
- Ensure CI pipeline passes with all tests enabled
- Add documentation for any complex fixes" \
  --test-strategy="1. Run full test suite locally
2. Fix each failing test
3. Verify CI pipeline passes
4. Monitor for flaky tests"

# Task 7: Finalize Supabase PNG Upload Integration (deferred)
task-master add-task \
  --title="Finalize Supabase PNG Upload Integration" \
  --description="Ensure mockup images upload correctly with error handling" \
  --priority=medium \
  --status=deferred \
  --dependencies="" \
  --details="Complete Supabase integration for PNG uploads:
- Implement reliable PNG upload to Supabase storage
- Add proper error handling and retry logic
- Ensure mockup images are correctly linked to businesses
- Implement CDN URL generation for uploaded images
- Add cleanup for orphaned images
- Include comprehensive error logging" \
  --test-strategy="1. Unit tests for upload logic
2. Integration tests with Supabase
3. Test error scenarios and retries
4. Verify CDN URL generation"

# Task 8: Add Unit and Integration Tests for Bounce Handling Logic
task-master add-task \
  --title="Add Unit and Integration Tests for Bounce Handling Logic" \
  --description="Simulate bounce scenarios and verify system responses" \
  --priority=high \
  --dependencies="" \
  --details="Implement comprehensive bounce handling tests:
- Unit tests for bounce detection logic
- Integration tests with SendGrid webhooks
- Simulate various bounce types (hard, soft, block)
- Test bounce threshold calculations
- Verify proper email status updates
- Test alerting and reporting mechanisms" \
  --test-strategy="1. Mock SendGrid webhook payloads
2. Test all bounce types
3. Verify database updates
4. Test threshold triggers"

# Task 9: Improve Error Propagation and Partial Failure Handling
task-master add-task \
  --title="Improve Error Propagation and Partial Failure Handling" \
  --description="Ensure failures are logged without breaking the batch process" \
  --priority=high \
  --dependencies="" \
  --details="Enhance error handling across the pipeline:
- Implement proper error propagation between pipeline stages
- Handle partial failures gracefully
- Continue processing valid items when some fail
- Add detailed error logging with context
- Implement error aggregation and reporting
- Add retry mechanisms for transient failures" \
  --test-strategy="1. Unit tests for error handling logic
2. Integration tests with failure scenarios
3. Test partial batch processing
4. Verify error reporting"

# Task 10: Add Test for Preflight Sequence
task-master add-task \
  --title="Add Test for Preflight Sequence" \
  --description="Write tests for the preflight check functionality" \
  --priority=medium \
  --dependencies="" \
  --details="Create comprehensive tests for preflight checks:
- Test all preflight validation steps
- Mock various failure scenarios
- Verify proper error messages
- Test environment variable validation
- Test API connectivity checks
- Test database connection validation" \
  --test-strategy="1. Unit tests for each preflight check
2. Integration tests for full sequence
3. Test various failure modes
4. Verify error reporting"

echo "All Phase 0 alignment review tasks have been added!"
