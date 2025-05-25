#!/usr/bin/env python3
"""
Test Prioritization Script

This script analyzes test dependencies and prioritizes tests for re-enablement
in the CI pipeline. It uses the test status tracker data to identify which tests
should be enabled next based on their dependencies, importance, and current status.

Usage:
    python scripts/prioritize_tests.py [--recommend=<num>] [--enable-recommended]

Options:
    --recommend=<num>    Number of tests to recommend for enabling (default: 5)
    --enable-recommended Enable the recommended tests automatically
"""

import argparse
import json
import os
import re
import sys
from typing import Set, Optional, Any, DefaultDict

# Use lowercase versions for Python 3.9 compatibility
# Use lowercase versions for Python 3.9 compatibility
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import typing modules
from typing import Dict, List

# Use lowercase versions for Python 3.9 compatibility

# Import test status tracker constants
from scripts.test_status_tracker import (
    STATUS_DISABLED,
    STATUS_FAILING,
    STATUS_PASSING,
    TestStatusTracker,
)

# Constants
TEST_DEPENDENCY_FILE = project_root / "scripts" / "test_dependencies.json"
TEST_PRIORITY_FILE = project_root / "scripts" / "test_priorities.json"


class TestDependencyGraph:
    """Graph representation of test dependencies."""

    def __init__(self):
        self.dependencies = {}  # test_id -> set of test_ids it depends on
        self.dependents = {}  # test_id -> set of test_ids that depend on it
        self.load_dependencies()

    def load_dependencies(self):
        """Load existing test dependencies from file."""
        if TEST_DEPENDENCY_FILE.exists():
            with open(TEST_DEPENDENCY_FILE) as f:
                dependencies = json.load(f)

            # Convert to sets
            self.dependencies = {k: set(v) for k, v in dependencies.items()}

            # Build dependents graph
            self.dependents = defaultdict(set)
            for test_id, deps in self.dependencies.items():
                for dep in deps:
                    self.dependents[dep].add(test_id)
        else:
            self.discover_dependencies()

    def save_dependencies(self):
        """Save current test dependencies to file."""
        # Convert sets to lists for JSON serialization
        dependencies_json = {k: list(v) for k, v in self.dependencies.items()}

        with open(TEST_DEPENDENCY_FILE, "w") as f:
            json.dump(dependencies_json, f, indent=2)

    def discover_dependencies(self):
        """Discover test dependencies by analyzing test files."""
        print("Discovering test dependencies...")

        # Get all test files
        test_files = list(project_root.glob("tests/test_*.py"))
        test_files.extend(project_root.glob("tests/**/test_*.py"))

        # Initialize dependency graph
        self.dependencies = {}

        # Analyze each test file
        for test_file in test_files:
            rel_path = test_file.relative_to(project_root)

            with open(test_file) as f:
                content = f.read()

            # Find test functions
            test_funcs = re.findall(r"def\s+(test_\w+)\s*\(", content)

            for func in test_funcs:
                test_id = f"{rel_path}::{func}"

                # Initialize empty dependency set
                self.dependencies[test_id] = set()

                # Look for imports and fixtures
                imports = re.findall(r"from\s+(\w+(?:\.\w+)*)\s+import", content)
                fixtures = re.findall(r"@pytest\.fixture", content)

                # Add dependencies based on imports
                for imp in imports:
                    if imp.startswith("tests."):
                        # This test depends on another test module
                        imp_path = imp.replace(".", "/") + ".py"
                        if Path(project_root / imp_path).exists():
                            self.dependencies[test_id].add(imp_path)

                # Add dependencies based on fixtures
                fixture_names = re.findall(
                    r"def\s+(\w+)\s*\(\s*\):\s*(?:[\'\"])(?:.*?)(?:[\'\"])\s*@pytest\.fixture",
                    content,
                )
                for fixture in fixture_names:
                    # Find tests that use this fixture
                    fixture_usage = re.findall(
                        rf"def\s+(test_\w+)\s*\(\s*.*?{fixture}.*?\):", content
                    )
                    if func in fixture_usage:
                        # Find where this fixture is defined
                        fixture_files = self.find_fixture_definition(fixture)
                        for fixture_file in fixture_files:
                            self.dependencies[test_id].add(fixture_file)

        # Build dependents graph
        self.dependents = defaultdict(set)
        for test_id, deps in self.dependencies.items():
            for dep in deps:
                self.dependents[dep].add(test_id)

        self.save_dependencies()
        print(f"Discovered dependencies for {len(self.dependencies)} tests")

    def find_fixture_definition(self, fixture_name: str) -> list[str]:
        """Find the file(s) where a fixture is defined."""
        fixture_files = []

        # Look in conftest.py files
        conftest_files = list(project_root.glob("**/conftest.py"))
        for conftest in conftest_files:
            rel_path = conftest.relative_to(project_root)
            with open(conftest) as f:
                content = f.read()

            if re.search(rf"def\s+{fixture_name}\s*\(", content):
                fixture_files.append(str(rel_path))

        return fixture_files

    def get_dependencies(self, test_id: str) -> set[str]:
        """Get all dependencies for a test (direct and indirect)."""
        if test_id not in self.dependencies:
            return set()

        # Direct dependencies
        all_deps = set(self.dependencies[test_id])

        # Indirect dependencies (recursive)
        for dep in list(all_deps):
            all_deps.update(self.get_dependencies(dep))

        return all_deps

    def get_dependents(self, test_id: str) -> set[str]:
        """Get all tests that depend on this test (direct and indirect)."""
        if test_id not in self.dependents:
            return set()

        # Direct dependents
        all_deps = set(self.dependents[test_id])

        # Indirect dependents (recursive)
        for dep in list(all_deps):
            all_deps.update(self.get_dependents(dep))

        return all_deps


class TestPrioritizer:
    """Prioritizes tests for re-enablement in the CI pipeline."""

    def __init__(self):
        self.tracker = TestStatusTracker()
        self.dependency_graph = TestDependencyGraph()
        self.priorities = self.load_priorities()

    def load_priorities(self) -> dict[str, int]:
        """Load test priorities from file or initialize from tracker."""
        if TEST_PRIORITY_FILE.exists():
            with open(TEST_PRIORITY_FILE) as f:
                return json.load(f)
        else:
            # Initialize from tracker priorities
            priorities = {}
            for test_id, test_info in self.tracker.tests.items():
                priorities[test_id] = test_info.get(
                    "priority", 3
                )  # Default to medium priority

            self.save_priorities(priorities)
            return priorities

    def save_priorities(self, priorities: dict[str, int]):
        """Save test priorities to file."""
        with open(TEST_PRIORITY_FILE, "w") as f:
            json.dump(priorities, f, indent=2)

    def calculate_test_scores(self) -> dict[str, float]:
        """Calculate a score for each test based on priority, dependencies, and status."""
        scores = {}

        for test_id, test_info in self.tracker.tests.items():
            # Skip tests that are already enabled
            if test_info["status"] != STATUS_DISABLED:
                continue

            # Base score from priority (1-5, where 1 is highest priority)
            priority = self.priorities.get(test_id, test_info.get("priority", 3))
            base_score = 6 - priority  # Invert so higher is better

            # Adjust score based on dependencies
            dependencies = self.dependency_graph.get_dependencies(test_id)
            dependency_factor = 1.0

            # Check if dependencies are passing
            for dep in dependencies:
                if dep in self.tracker.tests:
                    dep_status = self.tracker.tests[dep]["status"]
                    if dep_status == STATUS_FAILING:
                        # Heavily penalize tests with failing dependencies
                        dependency_factor *= 0.2
                    elif dep_status == STATUS_DISABLED:
                        # Penalize tests with disabled dependencies
                        dependency_factor *= 0.5

            # Adjust score based on dependents
            dependents = self.dependency_graph.get_dependents(test_id)
            dependent_bonus = min(
                len(dependents) * 0.2, 2.0
            )  # Cap at doubling the score

            # Calculate final score
            final_score = base_score * dependency_factor + dependent_bonus

            # Add category bonus
            category = test_info.get("category", "").lower()
            if category in ["core_utilities", "database"]:
                final_score *= 1.5  # 50% bonus for critical categories
            elif category in ["business_logic", "email"]:
                final_score *= 1.3  # 30% bonus for important categories

            scores[test_id] = final_score

        return scores

    def recommend_tests(self, num_tests: int = 5) -> list[tuple[str, float]]:
        """Recommend tests to enable next based on their scores."""
        scores = self.calculate_test_scores()

        # Sort tests by score (descending)
        sorted_tests = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_tests[:num_tests]

    def enable_tests(self, test_ids: list[str]):
        """Enable the specified tests in the test status tracker."""
        for test_id in test_ids:
            if test_id in self.tracker.tests:
                self.tracker.tests[test_id]["status"] = STATUS_PASSING
                print(f"Enabled test: {test_id}")

        self.tracker.save_status()
        print(f"Enabled {len(test_ids)} tests")

    def generate_report(self, recommended_tests: list[tuple[str, float]]):
        """Generate a report of recommended tests with their details."""
        report_lines = ["\n===== TEST PRIORITIZATION REPORT =====\n"]

        report_lines.append(
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        report_lines.append(f"Total tests: {len(self.tracker.tests)}")

        # Count tests by status
        status_counts: dict[str, int] = defaultdict(int)
        for test_info in self.tracker.tests.values():
            status_counts[test_info["status"]] += 1

        for status, count in status_counts.items():
            report_lines.append(f"  {status.upper()}: {count}")

        # Add recommended tests
        report_lines.append("\nRecommended tests to enable next:")
        for i, (test_id, score) in enumerate(recommended_tests, 1):
            test_info = self.tracker.tests[test_id]
            report_lines.append(f"{i}. {test_id} (Score: {score:.2f})")
            report_lines.append(
                f"   Category: {test_info.get('category', 'uncategorized')}"
            )
            report_lines.append(f"   Priority: {test_info.get('priority', 3)}")

            # Add dependency info
            dependencies = self.dependency_graph.get_dependencies(test_id)
            if dependencies:
                dep_statuses = []
                for dep in dependencies:
                    if dep in self.tracker.tests:
                        dep_status = self.tracker.tests[dep]["status"]
                        dep_statuses.append(f"{dep} ({dep_status})")

                if dep_statuses:
                    report_lines.append(
                        f"   Dependencies: {', '.join(dep_statuses[:3])}"
                        + (
                            f" and {len(dep_statuses) - 3} more"
                            if len(dep_statuses) > 3
                            else ""
                        )
                    )

            # Add dependent info
            dependents = self.dependency_graph.get_dependents(test_id)
            if dependents:
                report_lines.append(f"   Dependents: {len(dependents)} tests")

        # Add command to enable these tests
        test_ids = [test_id for test_id, _ in recommended_tests]
        report_lines.append("\nTo enable these tests, run:")
        report_lines.append(
            f"python scripts/prioritize_tests.py --enable-recommended --recommend={len(test_ids)}"
        )

        report_text = "\n".join(report_lines)
        print(report_text)

        # Write to file
        report_path = project_root / "test_results" / "prioritization_report.txt"
        os.makedirs(project_root / "test_results", exist_ok=True)
        with open(report_path, "w") as f:
            f.write(report_text)

        return report_text


def main():
    parser = argparse.ArgumentParser(description="Test Prioritization Script")
    parser.add_argument(
        "--recommend",
        type=int,
        default=5,
        help="Number of tests to recommend for enabling",
    )
    parser.add_argument(
        "--enable-recommended",
        action="store_true",
        help="Enable the recommended tests automatically",
    )

    args = parser.parse_args()

    prioritizer = TestPrioritizer()
    recommended_tests = prioritizer.recommend_tests(args.recommend)

    if args.enable_recommended:
        test_ids = [test_id for test_id, _ in recommended_tests]
        prioritizer.enable_tests(test_ids)

    prioritizer.generate_report(recommended_tests)

    return 0


if __name__ == "__main__":
    sys.exit(main())
