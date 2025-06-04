"""
Test Governance Framework.

Implements comprehensive guidelines, review processes, and ownership model
for maintaining stable tests in the CI pipeline.
Part of Task 14: CI Pipeline Test Monitoring and Governance Framework.
"""

import json
import logging
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


class TestOwnership(Enum):
    """Test ownership levels."""

    UNASSIGNED = "unassigned"
    INDIVIDUAL = "individual"
    TEAM = "team"
    CROSS_TEAM = "cross_team"
    INFRASTRUCTURE = "infrastructure"


class TestStatus(Enum):
    """Test status for governance tracking."""

    ACTIVE = "active"
    DISABLED = "disabled"
    QUARANTINED = "quarantined"
    DEPRECATED = "deprecated"
    UNDER_REVIEW = "under_review"


class Priority(Enum):
    """Test priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestOwnershipInfo:
    """Information about test ownership and governance."""

    test_id: str
    test_name: str
    test_suite: str
    file_path: str
    owner_type: TestOwnership
    owner_name: str
    owner_email: str
    team: str
    priority: Priority
    status: TestStatus
    created_date: datetime
    last_modified: datetime
    review_required: bool = False
    review_deadline: Optional[datetime] = None
    documentation_url: Optional[str] = None
    sla_hours: int = 24  # Hours to fix failing test
    notes: str = ""


@dataclass
class TestModificationRequest:
    """Request to modify or disable a test."""

    request_id: str
    test_id: str
    requested_by: str
    request_type: str  # "disable", "modify", "delete", "change_owner"
    justification: str
    proposed_changes: str
    status: str  # "pending", "approved", "rejected", "implemented"
    created_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    approval_required: bool = True


@dataclass
class TestReviewGuideline:
    """Guidelines for test reviews."""

    guideline_id: str
    title: str
    description: str
    category: str  # "stability", "performance", "maintainability", "documentation"
    severity: str  # "must", "should", "recommended"
    check_automated: bool = False
    check_function: Optional[str] = None  # Function name for automated check


class TestGovernanceManager:
    """Manages test governance, ownership, and review processes."""

    def __init__(self, governance_config_file: str = "test_governance.yml"):
        self.config_file = governance_config_file
        self.ownership_db: Dict[str, TestOwnershipInfo] = {}
        self.modification_requests: List[TestModificationRequest] = []
        self.review_guidelines: List[TestReviewGuideline] = []
        self.sla_configs: Dict[str, int] = {}

        self._load_configuration()
        self._setup_default_guidelines()
        self._discover_tests()

    def _load_configuration(self):
        """Load governance configuration."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file) as f:
                    config = yaml.safe_load(f)

                # Load SLA configurations
                self.sla_configs = config.get(
                    "sla_hours", {"critical": 4, "high": 12, "medium": 24, "low": 72}
                )

                # Load existing ownership data
                ownership_data = config.get("test_ownership", [])
                for data in ownership_data:
                    ownership_info = TestOwnershipInfo(**data)
                    self.ownership_db[ownership_info.test_id] = ownership_info

                logger.info(
                    f"Loaded governance configuration with {len(self.ownership_db)} test ownership records"
                )

        except Exception as e:
            logger.error(f"Error loading governance configuration: {e}")

    def _setup_default_guidelines(self):
        """Setup default review guidelines."""
        default_guidelines = [
            TestReviewGuideline(
                guideline_id="test_naming",
                title="Test Naming Convention",
                description="Tests must follow descriptive naming convention: test_<action>_<expected_result>",
                category="maintainability",
                severity="must",
                check_automated=True,
                check_function="check_test_naming",
            ),
            TestReviewGuideline(
                guideline_id="test_isolation",
                title="Test Isolation",
                description="Tests must be independent and not rely on execution order",
                category="stability",
                severity="must",
                check_automated=False,
            ),
            TestReviewGuideline(
                guideline_id="deterministic_assertions",
                title="Deterministic Assertions",
                description="Tests must have deterministic, non-flaky assertions",
                category="stability",
                severity="must",
                check_automated=False,
            ),
            TestReviewGuideline(
                guideline_id="timeout_handling",
                title="Timeout Configuration",
                description="Tests with external dependencies must have appropriate timeouts",
                category="stability",
                severity="must",
                check_automated=True,
                check_function="check_timeout_configuration",
            ),
            TestReviewGuideline(
                guideline_id="mock_usage",
                title="Proper Mock Usage",
                description="External dependencies should be mocked for unit tests",
                category="stability",
                severity="should",
                check_automated=True,
                check_function="check_mock_usage",
            ),
            TestReviewGuideline(
                guideline_id="test_documentation",
                title="Test Documentation",
                description="Complex tests must have clear docstrings explaining purpose",
                category="documentation",
                severity="should",
                check_automated=True,
                check_function="check_test_documentation",
            ),
            TestReviewGuideline(
                guideline_id="performance_bounds",
                title="Performance Test Bounds",
                description="Performance tests must have clearly defined acceptable bounds",
                category="performance",
                severity="must",
                check_automated=False,
            ),
            TestReviewGuideline(
                guideline_id="cleanup_resources",
                title="Resource Cleanup",
                description="Tests must clean up any resources they create",
                category="stability",
                severity="must",
                check_automated=False,
            ),
            TestReviewGuideline(
                guideline_id="error_messages",
                title="Clear Error Messages",
                description="Test failures must provide clear, actionable error messages",
                category="maintainability",
                severity="should",
                check_automated=False,
            ),
            TestReviewGuideline(
                guideline_id="test_data_management",
                title="Test Data Management",
                description="Tests must not depend on specific environment data",
                category="stability",
                severity="must",
                check_automated=False,
            ),
        ]

        self.review_guidelines = default_guidelines
        logger.info(f"Setup {len(default_guidelines)} default review guidelines")

    def _discover_tests(self):
        """Discover tests in the codebase and create ownership records."""
        test_files = self._find_test_files()

        for file_path in test_files:
            tests_in_file = self._extract_tests_from_file(file_path)

            for test_name in tests_in_file:
                test_id = f"{Path(file_path).stem}::{test_name}"

                if test_id not in self.ownership_db:
                    # Create default ownership record
                    ownership_info = TestOwnershipInfo(
                        test_id=test_id,
                        test_name=test_name,
                        test_suite=Path(file_path).stem,
                        file_path=file_path,
                        owner_type=TestOwnership.UNASSIGNED,
                        owner_name="unassigned",
                        owner_email="",
                        team="unassigned",
                        priority=Priority.MEDIUM,
                        status=TestStatus.ACTIVE,
                        created_date=self._get_file_creation_date(file_path),
                        last_modified=self._get_file_modification_date(file_path),
                    )

                    self.ownership_db[test_id] = ownership_info

        logger.info(f"Discovered {len(test_files)} test files with ownership tracking")

    def _find_test_files(self) -> List[str]:
        """Find test files in the project."""
        test_files = []
        test_patterns = ["test_*.py", "*_test.py", "test*.py"]

        # Look in common test directories
        test_dirs = ["tests", "test", "tests/unit", "tests/integration", "ci_tests"]

        for test_dir in test_dirs:
            if os.path.exists(test_dir):
                for pattern in test_patterns:
                    test_files.extend(Path(test_dir).rglob(pattern))

        return [str(f) for f in test_files]

    def _extract_tests_from_file(self, file_path: str) -> List[str]:
        """Extract test function names from a Python test file."""
        test_functions = []

        try:
            with open(file_path) as f:
                content = f.read()

            # Find test functions using regex
            test_pattern = r"def\s+(test_\w+)\s*\("
            matches = re.findall(test_pattern, content)
            test_functions.extend(matches)

            # Find test classes and their methods
            class_pattern = r"class\s+(Test\w+)\s*[:\(]"
            class_matches = re.findall(class_pattern, content)

            for class_name in class_matches:
                # Find methods in test classes
                class_section = re.search(
                    f"class\\s+{class_name}.*?(?=class\\s+|\\Z)", content, re.DOTALL
                )
                if class_section:
                    method_pattern = r"def\s+(test_\w+)\s*\("
                    method_matches = re.findall(method_pattern, class_section.group())
                    test_functions.extend(
                        [f"{class_name}::{method}" for method in method_matches]
                    )

        except Exception as e:
            logger.warning(f"Error extracting tests from {file_path}: {e}")

        return test_functions

    def _get_file_creation_date(self, file_path: str) -> datetime:
        """Get file creation date."""
        try:
            stat = os.stat(file_path)
            return datetime.fromtimestamp(stat.st_ctime)
        except:
            return datetime.now()

    def _get_file_modification_date(self, file_path: str) -> datetime:
        """Get file modification date."""
        try:
            stat = os.stat(file_path)
            return datetime.fromtimestamp(stat.st_mtime)
        except:
            return datetime.now()

    def assign_test_owner(
        self,
        test_id: str,
        owner_name: str,
        owner_email: str,
        team: str,
        priority: Priority = Priority.MEDIUM,
    ):
        """Assign ownership of a test."""
        if test_id in self.ownership_db:
            ownership_info = self.ownership_db[test_id]
            ownership_info.owner_type = TestOwnership.INDIVIDUAL
            ownership_info.owner_name = owner_name
            ownership_info.owner_email = owner_email
            ownership_info.team = team
            ownership_info.priority = priority
            ownership_info.sla_hours = self.sla_configs.get(priority.value, 24)

            logger.info(f"Assigned test {test_id} to {owner_name} ({team})")
            self._save_configuration()
        else:
            logger.error(f"Test {test_id} not found in ownership database")

    def request_test_modification(
        self,
        test_id: str,
        requested_by: str,
        request_type: str,
        justification: str,
        proposed_changes: str = "",
    ) -> str:
        """Submit a request to modify or disable a test."""
        request_id = (
            f"MOD_{int(datetime.now().timestamp())}_{len(self.modification_requests)}"
        )

        # Check if approval is required
        ownership_info = self.ownership_db.get(test_id)
        approval_required = True

        if ownership_info:
            # If requester is the owner, approval may not be required for minor changes
            if (
                ownership_info.owner_email == requested_by
                and request_type in ["modify", "change_owner"]
                and ownership_info.priority in [Priority.LOW, Priority.MEDIUM]
            ):
                approval_required = False

        request = TestModificationRequest(
            request_id=request_id,
            test_id=test_id,
            requested_by=requested_by,
            request_type=request_type,
            justification=justification,
            proposed_changes=proposed_changes,
            status="pending",
            created_at=datetime.now(),
            approval_required=approval_required,
        )

        self.modification_requests.append(request)
        logger.info(f"Test modification request {request_id} submitted for {test_id}")

        return request_id

    def review_modification_request(
        self, request_id: str, reviewer: str, decision: str, notes: str = ""
    ):
        """Review and approve/reject a modification request."""
        for request in self.modification_requests:
            if request.request_id == request_id:
                request.reviewed_by = reviewer
                request.reviewed_at = datetime.now()
                request.status = decision  # "approved", "rejected"

                if notes:
                    request.justification += f"\\n\\nReviewer notes: {notes}"

                logger.info(
                    f"Modification request {request_id} {decision} by {reviewer}"
                )

                # Auto-implement approved low-risk changes
                if decision == "approved" and request.request_type == "disable":
                    self._implement_test_disable(request.test_id, request.justification)

                break

    def _implement_test_disable(self, test_id: str, reason: str):
        """Implement test disabling with proper documentation."""
        ownership_info = self.ownership_db.get(test_id)
        if ownership_info:
            ownership_info.status = TestStatus.DISABLED
            ownership_info.notes += f"\\nDisabled: {reason} (Date: {datetime.now()})"

            # Update the actual test file with skip decorator
            self._add_skip_decorator(
                ownership_info.file_path, ownership_info.test_name, reason
            )

            logger.info(f"Test {test_id} disabled with reason: {reason}")

    def _add_skip_decorator(self, file_path: str, test_name: str, reason: str):
        """Add pytest.skip decorator to a test function."""
        try:
            with open(file_path) as f:
                content = f.read()

            # Find the test function and add skip decorator
            pattern = f"(def\\s+{test_name}\\s*\\([^\\)]*\\)\\s*:)"
            replacement = f'@pytest.mark.skip(reason="{reason}")\\n    \\1'

            updated_content = re.sub(pattern, replacement, content)

            # Add pytest import if not present
            if "import pytest" not in updated_content:
                updated_content = "import pytest\\n" + updated_content

            with open(file_path, "w") as f:
                f.write(updated_content)

            logger.info(f"Added skip decorator to {test_name} in {file_path}")

        except Exception as e:
            logger.error(f"Error adding skip decorator: {e}")

    def conduct_automated_review(self, test_id: str) -> Dict[str, Any]:
        """Conduct automated review of a test against guidelines."""
        ownership_info = self.ownership_db.get(test_id)
        if not ownership_info:
            return {"error": "Test not found"}

        results = {
            "test_id": test_id,
            "review_date": datetime.now().isoformat(),
            "guidelines_checked": [],
            "violations": [],
            "warnings": [],
            "score": 100,
        }

        # Check automated guidelines
        for guideline in self.review_guidelines:
            if guideline.check_automated and guideline.check_function:
                check_result = self._run_automated_check(guideline, ownership_info)
                results["guidelines_checked"].append(guideline.guideline_id)

                if not check_result["passed"]:
                    if guideline.severity == "must":
                        results["violations"].append(
                            {
                                "guideline": guideline.title,
                                "description": guideline.description,
                                "issue": check_result["issue"],
                            }
                        )
                        results["score"] -= 20
                    else:
                        results["warnings"].append(
                            {
                                "guideline": guideline.title,
                                "description": guideline.description,
                                "issue": check_result["issue"],
                            }
                        )
                        results["score"] -= 5

        results["score"] = max(0, results["score"])
        results["grade"] = self._calculate_review_grade(results["score"])

        return results

    def _run_automated_check(
        self, guideline: TestReviewGuideline, ownership_info: TestOwnershipInfo
    ) -> Dict[str, Any]:
        """Run an automated check function."""
        check_function = guideline.check_function

        if check_function == "check_test_naming":
            return self._check_test_naming(ownership_info)
        elif check_function == "check_timeout_configuration":
            return self._check_timeout_configuration(ownership_info)
        elif check_function == "check_mock_usage":
            return self._check_mock_usage(ownership_info)
        elif check_function == "check_test_documentation":
            return self._check_test_documentation(ownership_info)
        else:
            return {"passed": True, "issue": "Check not implemented"}

    def _check_test_naming(self, ownership_info: TestOwnershipInfo) -> Dict[str, Any]:
        """Check if test follows naming convention."""
        test_name = ownership_info.test_name

        # Check for descriptive naming: test_<action>_<expected_result>
        pattern = r"^test_\\w+_\\w+"

        if re.match(pattern, test_name):
            return {"passed": True, "issue": None}
        else:
            return {
                "passed": False,
                "issue": f"Test name '{test_name}' doesn't follow convention: test_<action>_<expected_result>",
            }

    def _check_timeout_configuration(
        self, ownership_info: TestOwnershipInfo
    ) -> Dict[str, Any]:
        """Check if test has appropriate timeout configuration."""
        try:
            with open(ownership_info.file_path) as f:
                content = f.read()

            # Look for timeout decorators or timeout parameters
            timeout_patterns = [
                r"@pytest\\.mark\\.timeout\\(",
                r"timeout\\s*=\\s*\\d+",
                r"@timeout\\(",
                r"with\\s+timeout\\(",
            ]

            for pattern in timeout_patterns:
                if re.search(pattern, content):
                    return {"passed": True, "issue": None}

            # Check if test has external dependencies (requests, database, etc.)
            external_patterns = [
                r"import\\s+requests",
                r"from\\s+requests",
                r"import\\s+psycopg2",
                r"import\\s+sqlite3",
                r"@mock\\.patch",
            ]

            has_external_deps = any(
                re.search(pattern, content) for pattern in external_patterns
            )

            if has_external_deps:
                return {
                    "passed": False,
                    "issue": "Test has external dependencies but no timeout configuration",
                }

            return {"passed": True, "issue": None}

        except Exception as e:
            return {"passed": False, "issue": f"Error checking file: {e}"}

    def _check_mock_usage(self, ownership_info: TestOwnershipInfo) -> Dict[str, Any]:
        """Check for proper mock usage in unit tests."""
        try:
            with open(ownership_info.file_path) as f:
                content = f.read()

            # Check if it's a unit test file
            if (
                "unit" not in ownership_info.file_path
                and "test_unit" not in ownership_info.test_name
            ):
                return {"passed": True, "issue": "Not a unit test"}

            # Look for external calls without mocking
            external_calls = [
                r"requests\\.(get|post|put|delete|patch)",
                r"urllib\\.",
                r"http\\.",
                r"psycopg2\\.",
                r"sqlite3\\.",
                r"os\\.system",
                r"subprocess\\.",
            ]

            mock_patterns = [
                r"@mock\\.patch",
                r"@patch",
                r"with\\s+mock\\.patch",
                r"Mock\\(",
                r"MagicMock\\(",
            ]

            has_external_calls = any(
                re.search(pattern, content) for pattern in external_calls
            )
            has_mocking = any(re.search(pattern, content) for pattern in mock_patterns)

            if has_external_calls and not has_mocking:
                return {
                    "passed": False,
                    "issue": "Unit test makes external calls without proper mocking",
                }

            return {"passed": True, "issue": None}

        except Exception as e:
            return {"passed": False, "issue": f"Error checking file: {e}"}

    def _check_test_documentation(
        self, ownership_info: TestOwnershipInfo
    ) -> Dict[str, Any]:
        """Check if test has adequate documentation."""
        try:
            with open(ownership_info.file_path) as f:
                content = f.read()

            # Find the specific test function
            test_name = ownership_info.test_name.split("::")[
                -1
            ]  # Handle class::method format

            # Look for docstring after function definition
            pattern = f'def\\s+{test_name}\\s*\\([^\\)]*\\)\\s*:\\s*"""([^"]*?)"""'
            match = re.search(pattern, content, re.DOTALL)

            if match:
                docstring = match.group(1).strip()
                if len(docstring) > 20:  # Minimum meaningful documentation
                    return {"passed": True, "issue": None}

            # Check for inline comments
            function_pattern = (
                f"def\\s+{test_name}\\s*\\([^\\)]*\\):(.*?)(?=def\\s+|class\\s+|\\Z)"
            )
            function_match = re.search(function_pattern, content, re.DOTALL)

            if function_match:
                function_body = function_match.group(1)
                comment_lines = [
                    line
                    for line in function_body.split("\\n")
                    if line.strip().startswith("#")
                ]

                if len(comment_lines) >= 2:  # At least some commenting
                    return {"passed": True, "issue": None}

            return {
                "passed": False,
                "issue": "Test lacks adequate documentation (docstring or comments)",
            }

        except Exception as e:
            return {"passed": False, "issue": f"Error checking documentation: {e}"}

    def _calculate_review_grade(self, score: int) -> str:
        """Calculate letter grade from review score."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def generate_sla_report(self) -> Dict[str, Any]:
        """Generate SLA compliance report."""
        from .test_monitoring import metrics_collector

        problematic_tests = metrics_collector.get_problematic_tests()
        sla_violations = []

        for test_metrics in problematic_tests:
            ownership_info = self.ownership_db.get(test_metrics.test_id)

            if ownership_info and test_metrics.pass_rate < 0.8:  # Failing test
                # Calculate time since failure started
                failure_duration = datetime.now() - test_metrics.last_execution
                sla_hours = ownership_info.sla_hours

                if failure_duration.total_seconds() > sla_hours * 3600:
                    sla_violations.append(
                        {
                            "test_id": test_metrics.test_id,
                            "test_name": test_metrics.test_name,
                            "owner": ownership_info.owner_name,
                            "team": ownership_info.team,
                            "priority": ownership_info.priority.value,
                            "sla_hours": sla_hours,
                            "failure_duration_hours": failure_duration.total_seconds()
                            / 3600,
                            "pass_rate": test_metrics.pass_rate,
                        }
                    )

        return {
            "report_date": datetime.now().isoformat(),
            "total_violations": len(sla_violations),
            "violations": sla_violations,
            "summary": {
                "critical_violations": len(
                    [v for v in sla_violations if v["priority"] == "critical"]
                ),
                "high_violations": len(
                    [v for v in sla_violations if v["priority"] == "high"]
                ),
                "medium_violations": len(
                    [v for v in sla_violations if v["priority"] == "medium"]
                ),
                "low_violations": len(
                    [v for v in sla_violations if v["priority"] == "low"]
                ),
            },
        }

    def get_governance_dashboard(self) -> Dict[str, Any]:
        """Get governance dashboard data."""
        total_tests = len(self.ownership_db)
        assigned_tests = len(
            [
                t
                for t in self.ownership_db.values()
                if t.owner_type != TestOwnership.UNASSIGNED
            ]
        )
        pending_requests = len(
            [r for r in self.modification_requests if r.status == "pending"]
        )

        ownership_breakdown = {}
        for ownership_type in TestOwnership:
            ownership_breakdown[ownership_type.value] = len(
                [
                    t
                    for t in self.ownership_db.values()
                    if t.owner_type == ownership_type
                ]
            )

        priority_breakdown = {}
        for priority in Priority:
            priority_breakdown[priority.value] = len(
                [t for t in self.ownership_db.values() if t.priority == priority]
            )

        status_breakdown = {}
        for status in TestStatus:
            status_breakdown[status.value] = len(
                [t for t in self.ownership_db.values() if t.status == status]
            )

        return {
            "total_tests": total_tests,
            "assigned_tests": assigned_tests,
            "assignment_rate": (
                (assigned_tests / total_tests * 100) if total_tests > 0 else 0
            ),
            "pending_requests": pending_requests,
            "ownership_breakdown": ownership_breakdown,
            "priority_breakdown": priority_breakdown,
            "status_breakdown": status_breakdown,
            "review_guidelines": len(self.review_guidelines),
            "sla_configs": self.sla_configs,
        }

    def _save_configuration(self):
        """Save governance configuration to file."""
        config = {
            "sla_hours": self.sla_configs,
            "test_ownership": [
                asdict(ownership) for ownership in self.ownership_db.values()
            ],
        }

        try:
            with open(self.config_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            logger.info("Governance configuration saved")
        except Exception as e:
            logger.error(f"Error saving governance configuration: {e}")


# Global governance manager instance
governance_manager = TestGovernanceManager()


def assign_test_owner(test_id: str, owner_name: str, owner_email: str, team: str):
    """Convenience function to assign test ownership."""
    governance_manager.assign_test_owner(test_id, owner_name, owner_email, team)


def request_test_disable(test_id: str, requested_by: str, justification: str) -> str:
    """Convenience function to request test disabling."""
    return governance_manager.request_test_modification(
        test_id, requested_by, "disable", justification
    )


if __name__ == "__main__":
    # Example usage
    logger.info("Test Governance Framework initialized")

    # Example: Assign ownership
    assign_test_owner(
        "test_user_auth::test_login_success",
        "John Doe",
        "john.doe@company.com",
        "backend-team",
    )

    # Example: Generate report
    dashboard = governance_manager.get_governance_dashboard()
    print(json.dumps(dashboard, indent=2))
