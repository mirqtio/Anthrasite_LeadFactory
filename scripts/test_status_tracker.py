#!/usr/bin/env python3
"""
Test Status Tracker

This script analyzes the test suite, categorizes tests, and tracks their status
during the incremental re-enablement process.

Usage:
    python scripts/test_status_tracker.py [--run-tests] [--categorize] [--report]

Options:
    --run-tests    Run all tests and record their status
    --categorize   Analyze and categorize tests by type
    --report       Generate a status report
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Constants
TEST_DIR = project_root / "tests"
STATUS_FILE = project_root / "scripts" / "test_status.json"
CATEGORIES = [
    "core_utilities",
    "business_logic",
    "integration",
    "api",
    "database",
    "email",
    "metrics",
    "other"
]

# Test status enum
STATUS_DISABLED = "disabled"
STATUS_FAILING = "failing"
STATUS_PASSING = "passing"
STATUS_SKIPPED = "skipped"

class TestStatusTracker:
    def __init__(self):
        self.tests = {}
        self.load_status()
    
    def load_status(self):
        """Load existing test status from file"""
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                self.tests = json.load(f)
        else:
            self.discover_tests()
    
    def save_status(self):
        """Save current test status to file"""
        with open(STATUS_FILE, "w") as f:
            json.dump(self.tests, f, indent=2)
    
    def discover_tests(self):
        """Discover all tests in the test directory"""
        print("Discovering tests...")
        
        # Find all test files
        test_files = list(TEST_DIR.glob("test_*.py"))
        test_files.extend(TEST_DIR.glob("**/test_*.py"))
        
        # Extract test functions from files
        for test_file in test_files:
            rel_path = test_file.relative_to(project_root)
            with open(test_file, "r") as f:
                content = f.read()
            
            # Find test functions (def test_*)
            test_funcs = re.findall(r"def\s+(test_\w+)\s*\(", content)
            
            # Add each test to our dictionary
            for func in test_funcs:
                test_id = f"{rel_path}::{func}"
                if test_id not in self.tests:
                    self.tests[test_id] = {
                        "file": str(rel_path),
                        "function": func,
                        "status": STATUS_DISABLED,  # All tests are initially disabled in CI
                        "category": "uncategorized",
                        "last_run": None,
                        "error_message": None,
                        "notes": "",
                        "priority": 3  # Default medium priority
                    }
        
        print(f"Discovered {len(self.tests)} tests")
    
    def categorize_tests(self):
        """Categorize tests based on their file name and content"""
        print("Categorizing tests...")
        
        for test_id, test_info in self.tests.items():
            file_path = project_root / test_info["file"]
            
            # Categorize based on filename
            filename = file_path.name
            
            if "unit" in filename:
                test_info["category"] = "core_utilities"
                test_info["priority"] = 1  # High priority
            elif any(x in filename for x in ["dedupe", "enrich", "score"]):
                test_info["category"] = "business_logic"
                test_info["priority"] = 2  # Medium-high priority
            elif any(x in filename for x in ["email", "unsubscribe"]):
                test_info["category"] = "email"
                test_info["priority"] = 2
            elif any(x in filename for x in ["metrics", "prometheus"]):
                test_info["category"] = "metrics"
                test_info["priority"] = 2
            elif "database" in filename or "schema" in filename:
                test_info["category"] = "database"
                test_info["priority"] = 1
            elif "scraper" in filename:
                test_info["category"] = "integration"
                test_info["priority"] = 3  # Medium-low priority
            else:
                # Read file content to better categorize
                with open(file_path, "r") as f:
                    content = f.read()
                
                if "requests" in content or "api" in content.lower():
                    test_info["category"] = "api"
                    test_info["priority"] = 3
                elif "db" in content or "database" in content or "cursor" in content:
                    test_info["category"] = "database"
                    test_info["priority"] = 2
                else:
                    test_info["category"] = "other"
                    test_info["priority"] = 4  # Low priority
        
        self.save_status()
        print("Categorization complete")
    
    def run_tests(self):
        """Run all tests and update their status"""
        print("Running tests...")
        
        # Create a temporary directory for test results
        os.makedirs(project_root / "test_results", exist_ok=True)
        
        # Run pytest with JSON output
        result = subprocess.run(
            ["pytest", "--json-report", "--json-report-file=test_results/report.json"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        # Parse the JSON report
        report_path = project_root / "test_results" / "report.json"
        if report_path.exists():
            with open(report_path, "r") as f:
                report = json.load(f)
            
            # Update test status based on report
            for test_id, test_info in report.get("tests", {}).items():
                if test_id in self.tests:
                    if test_info.get("outcome") == "passed":
                        self.tests[test_id]["status"] = STATUS_PASSING
                    elif test_info.get("outcome") == "skipped":
                        self.tests[test_id]["status"] = STATUS_SKIPPED
                    else:
                        self.tests[test_id]["status"] = STATUS_FAILING
                        self.tests[test_id]["error_message"] = test_info.get("call", {}).get("longrepr", "")
                    
                    self.tests[test_id]["last_run"] = datetime.now().isoformat()
        
        self.save_status()
        print(f"Test run complete. Exit code: {result.returncode}")
    
    def generate_report(self):
        """Generate a report of test status"""
        print("\n===== TEST STATUS REPORT =====\n")
        
        # Count tests by status and category
        status_counts = defaultdict(int)
        category_counts = defaultdict(lambda: defaultdict(int))
        
        for test_id, test_info in self.tests.items():
            status = test_info["status"]
            category = test_info["category"]
            
            status_counts[status] += 1
            category_counts[category][status] += 1
        
        # Print summary
        print(f"Total tests: {len(self.tests)}")
        for status, count in status_counts.items():
            print(f"  {status.upper()}: {count}")
        
        print("\nTests by category:")
        for category in sorted(category_counts.keys()):
            cat_total = sum(category_counts[category].values())
            print(f"  {category} ({cat_total}):")
            for status, count in category_counts[category].items():
                print(f"    {status.upper()}: {count}")
        
        # Print tests by priority
        priority_tests = defaultdict(list)
        for test_id, test_info in self.tests.items():
            priority_tests[test_info["priority"]].append(test_id)
        
        print("\nPriority 1 (Highest) tests to enable first:")
        for test_id in sorted(priority_tests[1]):
            test_info = self.tests[test_id]
            print(f"  - {test_info['file']}::{test_info['function']} ({test_info['category']})")
        
        # Print next steps
        print("\nRecommended next steps:")
        
        # Find disabled high priority tests
        high_priority_disabled = [
            test_id for test_id, test_info in self.tests.items()
            if test_info["status"] == STATUS_DISABLED and test_info["priority"] == 1
        ]
        
        if high_priority_disabled:
            print(f"1. Enable these {len(high_priority_disabled)} high-priority tests first:")
            for test_id in sorted(high_priority_disabled)[:5]:  # Show top 5
                test_info = self.tests[test_id]
                print(f"   - {test_info['file']}::{test_info['function']}")
            if len(high_priority_disabled) > 5:
                print(f"   - ... and {len(high_priority_disabled) - 5} more")
        else:
            # Find medium priority tests
            medium_priority_disabled = [
                test_id for test_id, test_info in self.tests.items()
                if test_info["status"] == STATUS_DISABLED and test_info["priority"] == 2
            ]
            if medium_priority_disabled:
                print(f"1. Enable these {len(medium_priority_disabled)} medium-priority tests:")
                for test_id in sorted(medium_priority_disabled)[:5]:  # Show top 5
                    test_info = self.tests[test_id]
                    print(f"   - {test_info['file']}::{test_info['function']}")
                if len(medium_priority_disabled) > 5:
                    print(f"   - ... and {len(medium_priority_disabled) - 5} more")

def main():
    parser = argparse.ArgumentParser(description="Test Status Tracker")
    parser.add_argument("--run-tests", action="store_true", help="Run all tests and record their status")
    parser.add_argument("--categorize", action="store_true", help="Analyze and categorize tests by type")
    parser.add_argument("--report", action="store_true", help="Generate a status report")
    
    args = parser.parse_args()
    
    tracker = TestStatusTracker()
    
    if args.categorize:
        tracker.categorize_tests()
    
    if args.run_tests:
        tracker.run_tests()
    
    if args.report or (not args.run_tests and not args.categorize):
        tracker.generate_report()

if __name__ == "__main__":
    main()
