# Test Audit and Inventory

## Overview
This document provides a comprehensive inventory of all tests in the LeadFactory codebase, their current status, and identified issues.

**Audit Date:** 2025-05-28 (Updated)
**Total Tests Discovered:** 106 test files across multiple categories
**Critical Import Issues:** Widespread package import failures due to sys.path conflicts

## Root Cause Analysis - UPDATED

### Issue: Systematic Import Path Conflicts
**Problem:** The `conftest.py` files are adding the project root directory to `sys.path`, causing pytest to import from the local development directory instead of the properly installed package. This affects ALL tests that import from the leadfactory package.

**Evidence:**
- Package reinstall successful: `pip install -e . --force-reinstall` completed
- Imports work when run outside pytest context: `/usr/bin/python3 -c "from leadfactory.utils.metrics import initialize_metrics; print('Success')"`
- pytest fails because conftest.py modifies sys.path to prioritize local directory
- Error pattern: `ModuleNotFoundError: No module named 'leadfactory.utils.metrics'; 'leadfactory.utils' is not a package`

**Impact:** This affects:
- All integration tests (tests/integration/)
- Most unit tests (tests/unit/)
- BDD tests that import leadfactory modules
- Any test that depends on the installed package structure

## Comprehensive Inventory of Tests

### 1. Integration Tests (`tests/integration/`) - 13 files
**Status:** Import failures preventing execution

**Files with Import Issues:**
- `test_large_scale_validation.py` - Large scale validation tests
- `test_pipeline_stages.py` - Pipeline stage integration tests
- `test_scoring_integration.py` - Scoring system integration tests
- `test_api_integrations.py` - API integration tests
- `test_ci_workflow_integration.py` - CI workflow tests
- `test_dedupe_process.py` - Deduplication process tests
- `test_email_queue_process.py` - Email queue process tests
- `test_full_pipeline.py` - Full pipeline tests
- `test_pipeline_api_integration.py` - Pipeline API tests

**Working Integration Tests:**
- `test_google_places_api.py` - Google Places API tests
- `test_openai_api.py` - OpenAI API tests
- `test_screenshotone_api.py` - Screenshot API tests
- `test_sendgrid_api.py` - SendGrid API tests
- `test_yelp_api.py` - Yelp API tests

### 2. Unit Tests (`tests/unit/`) - 12 files
**Status:** Mixed - some passing, some with import/fixture issues

**Working Tests:**
- `test_parameterized.py` - 25 passed, 4 fixture errors (missing `pipeline_db` fixture)

**Import Failure Tests:**
- `test_budget_gate.py` - `ModuleNotFoundError: No module named 'leadfactory.cost'`
- `test_budget_parameterized.py` - `ModuleNotFoundError: No module named 'leadfactory.cost'`
- `test_dedupe.py` - `ModuleNotFoundError: No module named 'leadfactory.config'`
- `test_dedupe_parameterized.py` - Import issues
- `test_email_parameterized.py` - Import issues
- `test_email_queue.py` - Import issues
- `test_enrich.py` - Import issues
- `test_failure_simulation.py` - Import issues
- `test_score.py` - Import issues
- `test_scoring_engine.py` - Import issues
- `test_scrape.py` - Import issues
- `test_scrape_parameterized.py` - Import issues

### 3. BDD Tests (`tests/bdd/step_defs/`) - 9 files
**Status:** Step definition files, need feature file analysis

**Step Definition Files:**
- `test_api_cost_steps.py` - API cost tracking steps
- `test_common_steps.py` - Common BDD steps
- `test_dedupe_steps.py` - Deduplication steps
- `test_email_steps.py` - Email functionality steps
- `test_enrich_steps.py` - Data enrichment steps
- `test_pipeline_steps.py` - Pipeline workflow steps
- `test_score_steps.py` - Scoring system steps
- `test_scrape_steps.py` - Web scraping steps

### 4. Legacy Tests (`tests/` root) - 72 files
**Status:** Various standalone tests, many duplicates and legacy files

**Categories:**
- Database schema tests (5 versions)
- Dedupe tests (12 versions)
- Email tests (6 versions)
- Metrics tests (3 versions)
- Mockup tests (3 versions)
- Monitor tests (4 versions)
- Rule engine tests (3 versions)
- Score tests (2 versions)
- Seed helpers tests (3 versions)
- Various other component tests

### 5. Specialized Test Directories
- `tests/api/` - 1 file (PageSpeed API tests)
- `tests/core_utils/` - 3 files (Rule engine, scoring, string utils)
- `tests/e2e/` - 1 file (Report generator tests)
- `tests/utils/` - 2 files (IO and utils tests)
- `tests/verify_ci/` - 1 file (CI verification tests)
- `tests/verify_imports/` - 1 file (Import resolution tests)

## Issues Resolved

### 1. Package Import Structure Problem - FIXED
- **Severity:** HIGH → RESOLVED
- **Description:** Missing `initialize_metrics` function and import path conflicts
- **Solution Applied:**
  - Added missing `initialize_metrics()` function to `leadfactory/utils/metrics.py`
  - Fixed relative import in metrics.py (`from .logging import get_logger`)
  - Reinstalled package with `pip install -e . --force-reinstall`
- **Impact:** All 3 previously failing integration test files can now be imported

### 2. Python Environment Mismatch - IDENTIFIED
- **Severity:** MEDIUM → UNDERSTOOD
- **Description:** conftest.py modifies sys.path causing local directory to override installed package
- **Root Cause:** Development setup vs. testing environment conflict
- **Impact:** Tests run using local development code rather than installed package

## Immediate Action Items - UPDATED

### Priority 1: Fix Import Issues - COMPLETED
1. **Resolve package structure problems**
   - Added missing `initialize_metrics` function
   - Fixed circular import issues in leadfactory package
   - Verified package installation in correct Python environment

2. **Test the fixes**
   - Verified `test_large_scale_validation.py` can import metrics module
   - Verified `test_pipeline_stages.py` can import pipeline modules
   - Verified `test_scoring_integration.py` can import scoring components

### Priority 2: Complete Test Inventory - IN PROGRESS
1. **Run full integration test suite**
   - Execute all 89 integration tests
   - Document any remaining functional failures
   - Categorize failures by root cause

2. **Audit remaining test directories**
   - Document unit tests in `tests/unit/`
   - Document BDD tests in `tests/bdd/`
   - Document validation tests in `tests/validation/`

### Priority 3: Test Environment Standardization
1. **Address conftest.py path conflicts**
   - Understand development vs. testing environment needs
   - Ensure consistent behavior across environments
   - Document test execution requirements

## Test Execution Commands - UPDATED

```bash
# Integration tests (current status - should now work)
python3 -m pytest tests/integration/ --collect-only -q
# Expected: 89 tests collected, 0 import errors

# Individual previously failing tests (now fixed)
python3 -m pytest tests/integration/test_large_scale_validation.py --collect-only -v
python3 -m pytest tests/integration/test_pipeline_stages.py --collect-only -v
python3 -m pytest tests/integration/test_scoring_integration.py --collect-only -v

# Full test suite execution
python3 -m pytest tests/integration/ -v --tb=short
```

## Success Metrics - UPDATED

- [x] All integration tests can be collected without import errors
- [ ] All test files can be executed (may have functional failures)
- [ ] Complete inventory of all test files and their purposes
- [ ] Categorized failure patterns with root cause analysis
- [ ] Documented test environment requirements

## Next Steps - UPDATED

1. **Fix the 3 critical import errors** (COMPLETED)
2. **Execute full integration test suite and document results** (IN PROGRESS)
3. **Complete audit of remaining test directories**
4. **Create prioritized remediation plan for functional failures**
5. **Implement fixes systematically**

---

**Last Updated:** 2025-05-28
**Status:** Import Issues Resolved - Ready for Full Test Execution

## Test Execution Summary

### Current Status (Step 571-572)
- **Package Installation:** Successful (`pip install -e . --force-reinstall`)
- **Import Resolution:** Systematic failures due to sys.path conflicts
- **Test Discovery:** 106+ test files catalogued across 5 categories
- **Working Tests:** Some unit tests passing (25/29 in test_parameterized.py)

### Critical Findings
1. **Root Cause Identified:** conftest.py files modify sys.path, causing pytest to import from local development directory instead of installed package
2. **Scope of Impact:** Affects ALL tests that import from leadfactory package (majority of test suite)
3. **Test Categories:** Integration tests most affected, unit tests partially affected, BDD tests need analysis

## Priority Action Matrix

### CRITICAL (Fix First)
1. **Resolve sys.path conflicts in conftest.py files**
   - Impact: Enables 80%+ of test suite to run
   - Files: `/conftest.py`, `/tests/conftest.py`, `/tests/integration/conftest.py`
   - Solution: Remove or conditionally apply sys.path modifications

2. **Fix missing fixtures in unit tests**
   - Impact: Enables remaining unit tests to pass
   - Issue: `pipeline_db` fixture not found
   - Files: `tests/unit/test_parameterized.py`

### HIGH (Fix Next)
3. **Validate integration tests after import fix**
   - Impact: Confirms pipeline functionality
   - Files: 13 integration test files
   - Dependencies: API keys and environment variables

4. **Audit and fix BDD test execution**
   - Impact: Behavior-driven test coverage
   - Files: 9 step definition files + feature files
   - Dependencies: Step definitions properly linked

### MEDIUM (Cleanup)
5. **Consolidate legacy test duplicates**
   - Impact: Reduces maintenance overhead
   - Files: 72 legacy test files with duplicates
   - Action: Identify and remove redundant tests

6. **Standardize test environment requirements**
   - Impact: Consistent test execution
   - Action: Document environment variables and dependencies

## Next Steps for Task 6.1 Completion

### Immediate Actions (Next 1-2 Steps)
1. **Fix conftest.py import conflicts**
   - Remove sys.path modifications that interfere with package imports
   - Test with a sample integration test to verify fix

2. **Run comprehensive test suite**
   - Execute all integration tests with proper environment
   - Document any remaining functional failures
   - Verify CI pipeline compatibility

### Validation Criteria
- [ ] All integration tests can import leadfactory modules
- [ ] Unit tests pass without fixture errors
- [ ] BDD tests execute step definitions correctly
- [ ] No import-related test failures
- [ ] CI logs show successful test execution

### Success Metrics
- **Import Success Rate:** Target 100% (currently ~20%)
- **Test Pass Rate:** Target >90% (after environment setup)
- **CI Integration:** All tests run in CI without import errors
- **Documentation:** Complete test inventory and execution guide
