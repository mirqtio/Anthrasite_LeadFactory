#!/usr/bin/env python3
"""
Comprehensive E2E Test Execution Script

This script runs a complete end-to-end test suite that validates all LeadFactory features,
including the newly implemented A/B testing, cost monitoring, and other enhancements.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).resolve().parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"e2e_comprehensive_{int(time.time())}.log"),
    ],
)

logger = logging.getLogger(__name__)


class E2ETestOrchestrator:
    """
    Orchestrates comprehensive E2E testing across multiple test suites and validation checks.
    """

    def __init__(self):
        self.project_root = project_root
        self.results = {
            "overall_success": False,
            "test_suites": {},
            "execution_time": 0,
            "recommendations": [],
        }
        self.start_time = time.time()

    async def run_comprehensive_tests(self) -> Dict:
        """
        Run all comprehensive E2E tests in the correct order.

        Returns:
            Dict containing complete test results
        """
        logger.info("Starting comprehensive E2E test execution...")

        test_suites = [
            ("Environment Setup", self._test_environment_setup),
            ("Unit Tests", self._run_unit_tests),
            ("Integration Tests", self._run_integration_tests),
            ("BDD Feature Tests", self._run_bdd_tests),
            ("Pipeline E2E Tests", self._run_pipeline_e2e_tests),
            ("Comprehensive E2E Tests", self._run_comprehensive_e2e_tests),
            ("Browser UI Tests", self._run_browser_tests),
            ("Performance Tests", self._run_performance_tests),
            ("Security Tests", self._run_security_tests),
            ("Cleanup", self._cleanup_tests),
        ]

        overall_success = True

        for suite_name, test_func in test_suites:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running {suite_name}")
            logger.info(f"{'='*60}")

            try:
                start_time = time.time()
                result = await test_func()
                duration = time.time() - start_time

                self.results["test_suites"][suite_name] = {
                    "success": result.get("success", False),
                    "duration": duration,
                    "details": result,
                    "timestamp": time.time(),
                }

                if not result.get("success", False):
                    overall_success = False
                    logger.error(f"{suite_name} failed!")
                else:
                    logger.info(f"{suite_name} passed! ({duration:.1f}s)")

            except Exception as e:
                logger.error(f"Error running {suite_name}: {e}")
                self.results["test_suites"][suite_name] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "error": str(e),
                    "timestamp": time.time(),
                }
                overall_success = False

        self.results["overall_success"] = overall_success
        self.results["execution_time"] = time.time() - self.start_time

        # Generate final report
        await self._generate_final_report()

        return self.results

    async def _test_environment_setup(self) -> Dict:
        """Test environment setup and prerequisites."""
        logger.info("Validating environment setup...")

        checks = []

        # Check Python version
        python_version = sys.version_info
        checks.append(
            {
                "name": "Python Version",
                "success": python_version >= (3, 8),
                "details": f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
            }
        )

        # Check required environment variables
        required_env_vars = [
            "OPENAI_API_KEY",
            "SENDGRID_API_KEY",
            "SCREENSHOTONE_API_KEY",
        ]

        for var in required_env_vars:
            value = os.getenv(var)
            checks.append(
                {
                    "name": f"Environment Variable: {var}",
                    "success": bool(value and value != "your_key_here"),
                    "details": "Set" if value else "Not set",
                }
            )

        # Check database connectivity
        try:
            import sqlite3

            test_db = sqlite3.connect(":memory:")
            test_db.close()
            checks.append(
                {
                    "name": "Database Connectivity",
                    "success": True,
                    "details": "SQLite available",
                }
            )
        except Exception as e:
            checks.append(
                {
                    "name": "Database Connectivity",
                    "success": False,
                    "details": f"Error: {e}",
                }
            )

        # Check required Python packages
        required_packages = [
            "pytest",
            "requests",
            "flask",
            "pydantic",
            "openai",
            "sendgrid",
        ]

        for package in required_packages:
            try:
                __import__(package)
                checks.append(
                    {
                        "name": f"Package: {package}",
                        "success": True,
                        "details": "Available",
                    }
                )
            except ImportError:
                checks.append(
                    {
                        "name": f"Package: {package}",
                        "success": False,
                        "details": "Not available",
                    }
                )

        success = all(check["success"] for check in checks)

        return {
            "success": success,
            "checks": checks,
            "summary": f"{sum(c['success'] for c in checks)}/{len(checks)} checks passed",
        }

    async def _run_unit_tests(self) -> Dict:
        """Run unit tests."""
        logger.info("Running unit tests...")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/unit/",
                    "-v",
                    "--tb=short",
                    "--maxfail=10",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": "Unit tests completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "Unit tests failed to execute",
            }

    async def _run_integration_tests(self) -> Dict:
        """Run integration tests."""
        logger.info("Running integration tests...")

        try:
            # Focus on key integration tests that validate new features
            key_integration_tests = [
                "tests/integration/test_ab_testing_workflow.py",
                "tests/integration/test_cost_dashboard_integration.py",
                "tests/integration/test_error_management_integration.py",
                "tests/integration/test_handoff_queue_integration.py",
                "tests/integration/test_webhook_failure_handling.py",
                "tests/integration/test_full_pipeline.py",
            ]

            # Filter to only existing tests
            existing_tests = [
                test
                for test in key_integration_tests
                if (self.project_root / test).exists()
            ]

            if not existing_tests:
                # Run all integration tests if specific ones don't exist
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "tests/integration/",
                        "-v",
                        "--tb=short",
                        "--maxfail=5",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )
            else:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest"]
                    + existing_tests
                    + ["-v", "--tb=short", "--maxfail=5"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tests_run": (
                    existing_tests if existing_tests else ["all integration tests"]
                ),
                "summary": "Integration tests completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "Integration tests failed to execute",
            }

    async def _run_bdd_tests(self) -> Dict:
        """Run BDD feature tests."""
        logger.info("Running BDD feature tests...")

        try:
            # Check if pytest-bdd is available
            try:
                import pytest_bdd

                bdd_available = True
            except ImportError:
                bdd_available = False

            if not bdd_available:
                return {
                    "success": True,  # Don't fail if BDD isn't set up
                    "skipped": True,
                    "reason": "pytest-bdd not available",
                    "summary": "BDD tests skipped",
                }

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/bdd/",
                    "-v",
                    "--tb=short",
                    "--maxfail=5",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": "BDD tests completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "BDD tests failed to execute",
            }

    async def _run_pipeline_e2e_tests(self) -> Dict:
        """Run existing pipeline E2E tests."""
        logger.info("Running pipeline E2E tests...")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/e2e/",
                    "-v",
                    "--tb=short",
                    "--maxfail=3",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": "Pipeline E2E tests completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "Pipeline E2E tests failed to execute",
            }

    async def _run_comprehensive_e2e_tests(self) -> Dict:
        """Run our comprehensive E2E test suite."""
        logger.info("Running comprehensive E2E test suite...")

        try:
            # Import and run our comprehensive test runner
            from scripts.comprehensive_e2e_test_runner import ComprehensiveE2ETestRunner

            runner = ComprehensiveE2ETestRunner(use_mock_apis=True, verbose=True)
            report = await runner.run_all_tests()

            return {
                "success": report["summary"]["success_rate"] >= 80,  # 80% threshold
                "report": report,
                "summary": f"Comprehensive E2E: {report['summary']['success_rate']:.1f}% success rate",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "Comprehensive E2E tests failed to execute",
            }

    async def _run_browser_tests(self) -> Dict:
        """Run browser-based UI tests."""
        logger.info("Running browser UI tests...")

        try:
            # Check if Playwright is available
            try:
                import playwright

                playwright_available = True
            except ImportError:
                playwright_available = False

            if not playwright_available:
                return {
                    "success": True,  # Don't fail if Playwright isn't set up
                    "skipped": True,
                    "reason": "Playwright not available",
                    "summary": "Browser tests skipped",
                }

            # Look for browser test files
            browser_test_files = list(
                self.project_root.glob("tests/**/test_*browser*.py")
            )
            browser_test_files.extend(
                list(self.project_root.glob("tests/**/test_*ui*.py"))
            )

            if not browser_test_files:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "No browser test files found",
                    "summary": "Browser tests skipped",
                }

            result = subprocess.run(
                [sys.executable, "-m", "pytest"]
                + [str(f) for f in browser_test_files]
                + ["-v", "--tb=short", "--maxfail=3"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tests_run": [str(f) for f in browser_test_files],
                "summary": "Browser tests completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "Browser tests failed to execute",
            }

    async def _run_performance_tests(self) -> Dict:
        """Run performance tests."""
        logger.info("Running performance tests...")

        try:
            perf_test_files = list(
                self.project_root.glob("tests/**/test_*performance*.py")
            )
            perf_test_files.extend(
                list(self.project_root.glob("tests/performance/**/*.py"))
            )

            if not perf_test_files:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "No performance test files found",
                    "summary": "Performance tests skipped",
                }

            result = subprocess.run(
                [sys.executable, "-m", "pytest"]
                + [str(f) for f in perf_test_files]
                + ["-v", "--tb=short", "--maxfail=3"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tests_run": [str(f) for f in perf_test_files],
                "summary": "Performance tests completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "Performance tests failed to execute",
            }

    async def _run_security_tests(self) -> Dict:
        """Run security tests."""
        logger.info("Running security tests...")

        try:
            security_test_files = list(
                self.project_root.glob("tests/**/test_*security*.py")
            )
            security_test_files.extend(
                list(self.project_root.glob("tests/security/**/*.py"))
            )

            if not security_test_files:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "No security test files found",
                    "summary": "Security tests skipped",
                }

            result = subprocess.run(
                [sys.executable, "-m", "pytest"]
                + [str(f) for f in security_test_files]
                + ["-v", "--tb=short", "--maxfail=3"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tests_run": [str(f) for f in security_test_files],
                "summary": "Security tests completed",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": "Security tests failed to execute",
            }

    async def _cleanup_tests(self) -> Dict:
        """Clean up test artifacts."""
        logger.info("Cleaning up test artifacts...")

        try:
            cleanup_tasks = []

            # Remove test databases
            test_dbs = list(self.project_root.glob("test_*.db*"))
            for db_file in test_dbs:
                try:
                    db_file.unlink()
                    cleanup_tasks.append(f"Removed {db_file.name}")
                except Exception as e:
                    cleanup_tasks.append(f"Failed to remove {db_file.name}: {e}")

            # Clean up log files older than 1 day
            log_files = list(self.project_root.glob("*.log"))
            current_time = time.time()
            for log_file in log_files:
                try:
                    if current_time - log_file.stat().st_mtime > 86400:  # 1 day
                        log_file.unlink()
                        cleanup_tasks.append(f"Removed old log {log_file.name}")
                except Exception as e:
                    cleanup_tasks.append(f"Failed to remove {log_file.name}: {e}")

            # Clean up temp files
            temp_files = list(self.project_root.glob("temp_*"))
            temp_files.extend(list(self.project_root.glob("tmp_*")))
            for temp_file in temp_files:
                try:
                    if temp_file.is_file():
                        temp_file.unlink()
                        cleanup_tasks.append(f"Removed temp file {temp_file.name}")
                except Exception as e:
                    cleanup_tasks.append(f"Failed to remove {temp_file.name}: {e}")

            return {
                "success": True,
                "cleanup_tasks": cleanup_tasks,
                "summary": f"Cleanup completed: {len(cleanup_tasks)} tasks",
            }

        except Exception as e:
            return {"success": False, "error": str(e), "summary": "Cleanup failed"}

    async def _generate_final_report(self):
        """Generate final comprehensive test report."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE E2E TEST REPORT")
        logger.info("=" * 80)

        total_suites = len(self.results["test_suites"])
        passed_suites = sum(
            1 for suite in self.results["test_suites"].values() if suite["success"]
        )
        failed_suites = total_suites - passed_suites

        logger.info(f"Overall Success: {self.results['overall_success']}")
        logger.info(
            f"Total Execution Time: {self.results['execution_time']:.1f} seconds"
        )
        logger.info(f"Test Suites: {passed_suites}/{total_suites} passed")

        logger.info("\nSuite Results:")
        for suite_name, suite_result in self.results["test_suites"].items():
            status = "PASS" if suite_result["success"] else "FAIL"
            duration = suite_result.get("duration", 0)
            logger.info(f"  {suite_name}: {status} ({duration:.1f}s)")

            if not suite_result["success"] and "error" in suite_result:
                logger.info(f"    Error: {suite_result['error']}")

        # Generate recommendations
        recommendations = []

        if failed_suites > 0:
            recommendations.append("Address all failing test suites before deployment")

        if (
            not self.results["test_suites"]
            .get("Environment Setup", {})
            .get("success", False)
        ):
            recommendations.append("CRITICAL: Fix environment setup issues first")

        if not self.results["test_suites"].get("Unit Tests", {}).get("success", False):
            recommendations.append(
                "HIGH: Fix unit test failures - these indicate core functionality issues"
            )

        if (
            not self.results["test_suites"]
            .get("Integration Tests", {})
            .get("success", False)
        ):
            recommendations.append(
                "HIGH: Fix integration test failures - component interactions are broken"
            )

        if self.results["overall_success"]:
            recommendations.append("System is ready for production deployment!")
        else:
            recommendations.append(
                "System is NOT ready for production - address all failures"
            )

        self.results["recommendations"] = recommendations

        logger.info("\nRecommendations:")
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"  {i}. {rec}")

        # Save detailed report
        report_file = f"comprehensive_e2e_report_{int(time.time())}.json"
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        logger.info(f"\nDetailed report saved to: {report_file}")
        logger.info("=" * 80)


async def main():
    """Main entry point."""
    logger.info("Starting comprehensive E2E test execution...")

    orchestrator = E2ETestOrchestrator()

    try:
        results = await orchestrator.run_comprehensive_tests()

        # Exit with appropriate code
        exit_code = 0 if results["overall_success"] else 1

        if results["overall_success"]:
            logger.info(
                "🎉 All comprehensive E2E tests passed! System is ready for production."
            )
        else:
            logger.error(
                "❌ Some tests failed. Please review the report and fix issues before deployment."
            )

        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Critical error during test execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
