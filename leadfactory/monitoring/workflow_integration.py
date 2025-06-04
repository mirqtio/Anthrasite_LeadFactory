"""
Development Workflow Integration for Test Monitoring.

Integrates test monitoring with GitHub, issue tracking, code review processes,
and development tools for seamless CI/CD pipeline governance.
Part of Task 14: CI Pipeline Test Monitoring and Governance Framework.
"""

import json
import logging
import os
import subprocess
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from .test_alerting import Alert, alert_manager
from .test_analytics import PredictionResult, analytics_engine
from .test_governance import governance_manager
from .test_monitoring import TestMetrics, metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class GitHubIssue:
    """GitHub issue for test failures."""

    issue_number: int
    title: str
    body: str
    labels: List[str]
    assignees: List[str]
    state: str
    created_at: datetime
    test_id: str


@dataclass
class PullRequestCheck:
    """Test health check for pull requests."""

    pr_number: int
    commit_sha: str
    affected_tests: List[str]
    unstable_tests: List[str]
    risk_assessment: str  # "low", "medium", "high"
    recommendations: List[str]
    check_status: str  # "pending", "success", "failure"


class GitHubIntegration:
    """Integration with GitHub for automated issue creation and PR checks."""

    def __init__(self, repo_owner: str, repo_name: str, token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def create_test_failure_issue(
        self, test_metrics: TestMetrics, alert: Alert
    ) -> Optional[GitHubIssue]:
        """Create GitHub issue for test failure."""
        # Check if issue already exists for this test
        existing_issue = self._find_existing_test_issue(test_metrics.test_id)
        if existing_issue:
            logger.info(
                f"Issue already exists for test {test_metrics.test_id}: #{existing_issue.issue_number}"
            )
            return existing_issue

        # Generate issue content
        title = f"Test Failure: {test_metrics.test_name} ({alert.severity.upper()})"

        body = f"""
## Test Failure Alert

**Test**: {test_metrics.test_name}
**Suite**: {test_metrics.test_suite}
**Severity**: {alert.severity.upper()}
**Alert Triggered**: {alert.triggered_at}

### Current Metrics
- **Pass Rate**: {test_metrics.pass_rate:.1%}
- **Flakiness Score**: {test_metrics.flakiness_score:.1%}
- **Reliability Grade**: {test_metrics.reliability_grade}
- **Trend**: {test_metrics.trend}
- **Executions**: {test_metrics.execution_count}

### Alert Details
{alert.message}

### Recommended Actions
"""

        # Add recommendations based on the alert
        if alert.severity in ["high", "critical"]:
            body += "- 🚨 **Immediate attention required**\\n"
            body += "- Investigate root cause and fix within SLA\\n"

        if test_metrics.flakiness_score > 0.3:
            body += "- 🔄 Test shows flaky behavior - review test isolation\\n"

        if test_metrics.reliability_grade in ["D", "F"]:
            body += "- 📊 Test has poor reliability - consider refactoring\\n"

        body += """
### Owner Information
"""

        # Get ownership information
        ownership_info = governance_manager.ownership_db.get(test_metrics.test_id)
        if ownership_info:
            body += f"- **Owner**: {ownership_info.owner_name}\\n"
            body += f"- **Team**: {ownership_info.team}\\n"
            body += f"- **SLA**: {ownership_info.sla_hours} hours\\n"
        else:
            body += "- **Owner**: Unassigned\\n"

        body += f"""
### Test File
- **Location**: {ownership_info.file_path if ownership_info else "Unknown"}

---
*This issue was automatically created by the CI Pipeline Test Monitoring system.*
*Issue ID: {alert.alert_id}*
"""

        # Determine labels
        labels = ["test-failure", f"severity-{alert.severity}"]
        if test_metrics.flakiness_score > 0.3:
            labels.append("flaky-test")
        if test_metrics.reliability_grade in ["D", "F"]:
            labels.append("reliability-issue")

        # Determine assignees
        assignees = []
        if ownership_info and ownership_info.owner_email:
            # Convert email to GitHub username (this would need configuration)
            github_username = self._email_to_github_username(ownership_info.owner_email)
            if github_username:
                assignees.append(github_username)

        # Create the issue
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues"
        data = {"title": title, "body": body, "labels": labels, "assignees": assignees}

        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()

            issue_data = response.json()

            github_issue = GitHubIssue(
                issue_number=issue_data["number"],
                title=title,
                body=body,
                labels=labels,
                assignees=assignees,
                state="open",
                created_at=datetime.now(),
                test_id=test_metrics.test_id,
            )

            logger.info(
                f"Created GitHub issue #{github_issue.issue_number} for test {test_metrics.test_id}"
            )
            return github_issue

        except Exception as e:
            logger.error(f"Failed to create GitHub issue: {e}")
            return None

    def _find_existing_test_issue(self, test_id: str) -> Optional[GitHubIssue]:
        """Find existing open issue for a test."""
        try:
            # Search for open issues with the test ID in the body
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues"
            params = {
                "state": "open",
                "labels": "test-failure",
                "sort": "created",
                "direction": "desc",
            }

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            issues = response.json()

            for issue in issues:
                if test_id in issue.get("body", ""):
                    return GitHubIssue(
                        issue_number=issue["number"],
                        title=issue["title"],
                        body=issue["body"],
                        labels=[label["name"] for label in issue["labels"]],
                        assignees=[
                            assignee["login"] for assignee in issue["assignees"]
                        ],
                        state=issue["state"],
                        created_at=datetime.fromisoformat(
                            issue["created_at"].replace("Z", "+00:00")
                        ),
                        test_id=test_id,
                    )

            return None

        except Exception as e:
            logger.error(f"Error searching for existing issues: {e}")
            return None

    def _email_to_github_username(self, email: str) -> Optional[str]:
        """Convert email to GitHub username (requires configuration mapping)."""
        # This would need to be configured with actual email-to-username mappings
        # For now, return None
        return None

    def check_pull_request_tests(
        self, pr_number: int, commit_sha: str
    ) -> PullRequestCheck:
        """Check test health for a pull request."""
        # Get changed files in the PR
        changed_files = self._get_pr_changed_files(pr_number)

        # Identify potentially affected tests
        affected_tests = self._identify_affected_tests(changed_files)

        # Check stability of affected tests
        unstable_tests = []
        risk_factors = []

        for test_id in affected_tests:
            prediction = analytics_engine.predict_test_instability(test_id)
            if prediction and prediction.risk_level in ["high", "critical"]:
                unstable_tests.append(test_id)
                risk_factors.extend(prediction.contributing_factors)

        # Assess overall risk
        if len(unstable_tests) >= 3:
            risk_assessment = "high"
        elif len(unstable_tests) >= 1:
            risk_assessment = "medium"
        else:
            risk_assessment = "low"

        # Generate recommendations
        recommendations = self._generate_pr_recommendations(
            affected_tests, unstable_tests, risk_factors
        )

        # Determine check status
        if risk_assessment == "high":
            check_status = "failure"
        elif risk_assessment == "medium":
            check_status = "failure"  # Require attention
        else:
            check_status = "success"

        pr_check = PullRequestCheck(
            pr_number=pr_number,
            commit_sha=commit_sha,
            affected_tests=affected_tests,
            unstable_tests=unstable_tests,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            check_status=check_status,
        )

        # Create GitHub status check
        self._create_status_check(commit_sha, pr_check)

        return pr_check

    def _get_pr_changed_files(self, pr_number: int) -> List[str]:
        """Get list of files changed in a pull request."""
        try:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/files"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            files_data = response.json()
            return [file_data["filename"] for file_data in files_data]

        except Exception as e:
            logger.error(f"Error getting PR changed files: {e}")
            return []

    def _identify_affected_tests(self, changed_files: List[str]) -> List[str]:
        """Identify tests that might be affected by file changes."""
        affected_tests = []

        # Get all test ownership records
        for test_id, ownership_info in governance_manager.ownership_db.items():
            test_file_base = (
                ownership_info.file_path.replace(".py", "")
                .replace("test_", "")
                .replace("_test", "")
            )

            for changed_file in changed_files:
                changed_file_base = changed_file.replace(".py", "")

                # Simple heuristic: if test file name relates to changed file
                if (
                    test_file_base in changed_file_base
                    or changed_file_base in test_file_base
                    or ownership_info.test_suite in changed_file
                ):
                    affected_tests.append(test_id)
                    break

        return list(set(affected_tests))  # Remove duplicates

    def _generate_pr_recommendations(
        self,
        affected_tests: List[str],
        unstable_tests: List[str],
        risk_factors: List[str],
    ) -> List[str]:
        """Generate recommendations for PR based on test analysis."""
        recommendations = []

        if not affected_tests:
            recommendations.append(
                "✅ No tests appear to be directly affected by these changes"
            )
            return recommendations

        recommendations.append(
            f"📊 {len(affected_tests)} tests may be affected by these changes"
        )

        if unstable_tests:
            recommendations.append(
                f"⚠️ {len(unstable_tests)} potentially unstable tests detected"
            )
            recommendations.append(
                "🔍 Consider running affected tests multiple times to verify stability"
            )

        if "Low pass rate" in risk_factors:
            recommendations.append(
                "📉 Some affected tests have historically low pass rates"
            )

        if "High flakiness" in risk_factors:
            recommendations.append("🔄 Some affected tests show flaky behavior")

        if "Degrading performance trend" in risk_factors:
            recommendations.append(
                "📈 Some affected tests show degrading performance trends"
            )

        if len(affected_tests) > 10:
            recommendations.append(
                "🎯 Large number of tests affected - consider breaking changes into smaller PRs"
            )

        return recommendations

    def _create_status_check(self, commit_sha: str, pr_check: PullRequestCheck):
        """Create GitHub status check for the commit."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/statuses/{commit_sha}"

        # Create description based on results
        if pr_check.check_status == "success":
            description = f"Test health check passed. {len(pr_check.affected_tests)} tests analyzed."
            state = "success"
        else:
            description = f"Test health concerns detected. {len(pr_check.unstable_tests)} unstable tests."
            state = "failure"

        data = {
            "state": state,
            "description": description,
            "context": "ci/test-health-check",
            "target_url": "",  # Could link to detailed report
        }

        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            logger.info(f"Created status check for commit {commit_sha}: {state}")
        except Exception as e:
            logger.error(f"Failed to create status check: {e}")


class IDEIntegration:
    """Integration with IDEs for test health information."""

    def __init__(self):
        self.metrics_cache = {}
        self.cache_refresh_interval = 300  # 5 minutes
        self.last_cache_refresh = datetime.min

    def get_test_health_info(self, file_path: str) -> Dict[str, Any]:
        """Get test health information for a file."""
        self._refresh_cache_if_needed()

        # Find tests in the file
        test_ids = self._find_tests_in_file(file_path)

        if not test_ids:
            return {"status": "no_tests", "tests": []}

        test_health = []
        overall_health = "healthy"

        for test_id in test_ids:
            metrics = self.metrics_cache.get(test_id)
            if metrics:
                health_info = {
                    "test_id": test_id,
                    "test_name": metrics.test_name,
                    "pass_rate": metrics.pass_rate,
                    "flakiness_score": metrics.flakiness_score,
                    "reliability_grade": metrics.reliability_grade,
                    "trend": metrics.trend,
                    "status": self._determine_test_status(metrics),
                }

                test_health.append(health_info)

                # Update overall health
                if health_info["status"] == "critical":
                    overall_health = "critical"
                elif (
                    health_info["status"] == "warning" and overall_health != "critical"
                ):
                    overall_health = "warning"

        return {
            "status": overall_health,
            "tests": test_health,
            "summary": {
                "total_tests": len(test_health),
                "healthy_tests": len(
                    [t for t in test_health if t["status"] == "healthy"]
                ),
                "warning_tests": len(
                    [t for t in test_health if t["status"] == "warning"]
                ),
                "critical_tests": len(
                    [t for t in test_health if t["status"] == "critical"]
                ),
            },
        }

    def _refresh_cache_if_needed(self):
        """Refresh metrics cache if needed."""
        if (
            datetime.now() - self.last_cache_refresh
        ).total_seconds() > self.cache_refresh_interval:
            self._refresh_metrics_cache()

    def _refresh_metrics_cache(self):
        """Refresh the metrics cache."""
        all_tests = metrics_collector.get_all_test_metrics(limit=1000)
        self.metrics_cache = {test.test_id: test for test in all_tests}
        self.last_cache_refresh = datetime.now()
        logger.info(f"Refreshed IDE metrics cache with {len(self.metrics_cache)} tests")

    def _find_tests_in_file(self, file_path: str) -> List[str]:
        """Find test IDs for tests in a file."""
        test_ids = []

        for test_id, ownership_info in governance_manager.ownership_db.items():
            if ownership_info.file_path == file_path:
                test_ids.append(test_id)

        return test_ids

    def _determine_test_status(self, metrics: TestMetrics) -> str:
        """Determine test status based on metrics."""
        if metrics.reliability_grade in ["D", "F"] or metrics.pass_rate < 0.5:
            return "critical"
        elif metrics.flakiness_score > 0.3 or metrics.pass_rate < 0.8:
            return "warning"
        else:
            return "healthy"


class WorkflowIntegrationManager:
    """Main manager for development workflow integration."""

    def __init__(self, github_config: Optional[Dict[str, str]] = None):
        self.github_integration = None
        self.ide_integration = IDEIntegration()
        self.auto_issue_creation = True
        self.auto_pr_checks = True

        if github_config:
            self.github_integration = GitHubIntegration(
                repo_owner=github_config["repo_owner"],
                repo_name=github_config["repo_name"],
                token=github_config["token"],
            )

        # Set up alert handling
        self._setup_alert_handlers()

    def _setup_alert_handlers(self):
        """Setup handlers for alerts to create GitHub issues."""
        # This would integrate with the alerting system
        pass

    def handle_test_alert(self, alert: Alert):
        """Handle test alert by creating GitHub issue if needed."""
        if not self.github_integration or not self.auto_issue_creation:
            return

        # Get test metrics
        test_metrics = metrics_collector.get_test_metrics(alert.test_id)
        if not test_metrics:
            return

        # Only create issues for significant alerts
        if alert.severity in ["high", "critical"]:
            github_issue = self.github_integration.create_test_failure_issue(
                test_metrics, alert
            )
            if github_issue:
                logger.info(
                    f"Created GitHub issue #{github_issue.issue_number} for alert {alert.alert_id}"
                )

    def check_pull_request(
        self, pr_number: int, commit_sha: str
    ) -> Optional[PullRequestCheck]:
        """Check pull request for test health issues."""
        if not self.github_integration or not self.auto_pr_checks:
            return None

        return self.github_integration.check_pull_request_tests(pr_number, commit_sha)

    def get_test_health_for_file(self, file_path: str) -> Dict[str, Any]:
        """Get test health information for IDE integration."""
        return self.ide_integration.get_test_health_info(file_path)

    def generate_code_review_report(self, pr_number: int) -> Dict[str, Any]:
        """Generate test health report for code review."""
        if not self.github_integration:
            return {"error": "GitHub integration not configured"}

        # Get PR information
        try:
            url = f"{self.github_integration.base_url}/repos/{self.github_integration.repo_owner}/{self.github_integration.repo_name}/pulls/{pr_number}"
            response = requests.get(url, headers=self.github_integration.headers)
            response.raise_for_status()
            pr_data = response.json()

            commit_sha = pr_data["head"]["sha"]

            # Run test health check
            pr_check = self.check_pull_request(pr_number, commit_sha)

            if not pr_check:
                return {"error": "Could not perform test health check"}

            # Get detailed predictions for affected tests
            detailed_predictions = []
            for test_id in pr_check.affected_tests:
                prediction = analytics_engine.predict_test_instability(test_id)
                if prediction:
                    detailed_predictions.append(asdict(prediction))

            report = {
                "pr_number": pr_number,
                "commit_sha": commit_sha,
                "test_health_check": asdict(pr_check),
                "detailed_predictions": detailed_predictions,
                "overall_recommendation": self._generate_overall_recommendation(
                    pr_check
                ),
                "generated_at": datetime.now().isoformat(),
            }

            return report

        except Exception as e:
            logger.error(f"Error generating code review report: {e}")
            return {"error": str(e)}

    def _generate_overall_recommendation(self, pr_check: PullRequestCheck) -> str:
        """Generate overall recommendation for PR."""
        if pr_check.risk_assessment == "high":
            return "❌ **High Risk**: This PR affects multiple unstable tests. Consider addressing test stability before merging."
        elif pr_check.risk_assessment == "medium":
            return "⚠️ **Medium Risk**: Some affected tests show instability. Monitor closely after merge."
        else:
            return "✅ **Low Risk**: No significant test stability concerns detected."


# Configuration and initialization
def setup_workflow_integration(
    github_repo_owner: str = None,
    github_repo_name: str = None,
    github_token: str = None,
) -> WorkflowIntegrationManager:
    """Setup workflow integration with optional GitHub configuration."""
    github_config = None

    if all([github_repo_owner, github_repo_name, github_token]):
        github_config = {
            "repo_owner": github_repo_owner,
            "repo_name": github_repo_name,
            "token": github_token,
        }

    return WorkflowIntegrationManager(github_config)


# Global workflow integration manager
workflow_manager = setup_workflow_integration(
    github_repo_owner=os.getenv("GITHUB_REPO_OWNER"),
    github_repo_name=os.getenv("GITHUB_REPO_NAME"),
    github_token=os.getenv("GITHUB_TOKEN"),
)


def create_test_issue_for_alert(alert: Alert):
    """Convenience function to create GitHub issue for alert."""
    workflow_manager.handle_test_alert(alert)


def check_pr_test_health(pr_number: int, commit_sha: str) -> Optional[PullRequestCheck]:
    """Convenience function to check PR test health."""
    return workflow_manager.check_pull_request(pr_number, commit_sha)


if __name__ == "__main__":
    # Example usage
    logger.info("Workflow Integration initialized")

    # Example: Check test health for a file
    test_health = workflow_manager.get_test_health_for_file("tests/test_example.py")
    print(json.dumps(test_health, indent=2))
